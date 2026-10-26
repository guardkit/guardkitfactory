"""The owner's run profile is locked read-only once a launch passes.

18 October 2026 (build FEAT-05EE, and FEAT-B463 on 11 October): GuardKit reuses
one dcode run profile for every Player turn in its process. A model's command
wrote ``full.log`` into it after a clean turn, and the launch check refused
every later turn. With ``lock_profile_identity`` (set only by the profile's
owner, to the directory's device and inode recorded when it made it) the
factory makes the clean profile read-only right after the launch check passes,
so such a write fails inside the command and the next turn launches.

26 October 2026 (step 2, census GKF-035, GKF-036, GKF-077 and GKF-078): a
profile holding more than the clean shape, one that cannot be locked, one that
is not writable and a malformed lock identity are logged; the launch goes on.

Real offline dcode graphs with fake provider HTTP, like ``test_dcode_harness``.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import stat
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from guardkit.orchestrator.harness import ResultMessageEvent

from guardkitfactory.harness.langgraph_harness import LangGraphHarness
from guardkitfactory.harness.player_config import build_player_config

from .test_dcode_harness import Exchange, isolate  # noqa: F401 - autouse fixture
from .test_player_skills_graph import _backend, _close_clients, _collect, _model, _scaffold

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 12) or importlib.util.find_spec("deepagents_code") is None,
    reason="dcode graph acceptance requires Python 3.12+ and the required dependency",
)


@pytest.fixture
def profile() -> Any:
    """The process-wide profile, left writable and empty for the next test."""

    root = Path(os.environ["DEEPAGENTS_HOME"]).resolve()
    assert not any(root.iterdir()) or _writable(root)
    yield root
    for directory, _dirs, _files in os.walk(root):
        os.chmod(directory, 0o700)
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_symlink() or path.is_file():
            path.unlink()
        else:
            path.rmdir()


def _writable(path: Path) -> bool:
    return bool(path.lstat().st_mode & 0o222)


def _modes(root: Path) -> dict[str, int]:
    return {
        str(path.relative_to(root)): stat.S_IMODE(path.lstat().st_mode)
        for path in [root, *root.rglob("*")]
    }


def _config(repo: Path, profile: Path, *, lock: bool) -> Any:
    extra = {"lock_profile_identity": _identity(profile)} if lock else {}
    return build_player_config(
        cwd=repo,
        dcode_home=profile,
        skills=["skills"],
        memory=["AGENTS.md"],
        repository_instructions=["AGENTS.md"],
        declared_commands=[("test", "./qa/run-suite.sh --exact")],
        **extra,
    )


def _skill_reads(repo: Path) -> list[tuple[str, dict[str, object]]]:
    root = (repo / "skills").resolve()
    return [
        ("read_file", {"file_path": str(root / "planning/SKILL.md"), "limit": 1000}),
        ("read_file", {"file_path": str(root / "code-review/SKILL.md"), "limit": 1000}),
    ]


def _turn(repo: Path, config: Any, calls: list[tuple[str, dict[str, object]]]) -> Exchange:
    """One Player invocation; returns its exchange (each request's body)."""

    exchange = Exchange([*_skill_reads(repo), *calls])
    model, sync, async_ = _model(exchange)
    try:
        harness = LangGraphHarness(model, backend=_backend(repo), player_config=config)
        events = asyncio.run(_collect(harness, repo))
        assert any(isinstance(event, ResultMessageEvent) for event in events)
        return exchange
    finally:
        _close_clients(sync, async_)


def _tool_outputs(exchange: Exchange) -> list[str]:
    return [
        str(message.get("content"))
        for message in exchange.bodies[-1]["messages"]
        if message.get("role") == "tool"
    ]


def test_turn_one_makes_the_skeleton_then_later_turns_launch_and_a_stray_write_fails(
    tmp_path: Path, profile: Path
) -> None:
    repo = _scaffold(tmp_path)
    config = _config(repo, profile, lock=True)
    assert config.lock_profile_identity == _identity(profile)

    # Turn 1: the profile is writable and empty; dcode makes its skeleton,
    # the launch check passes, then the profile is locked.
    _turn(repo, config, [("execute", {"command": "echo turn one"})])
    modes = _modes(profile)
    assert set(modes) == {
        ".",
        "guardkit-player",
        "guardkit-player/skills",
        "guardkit-player/AGENTS.md",
    }
    assert all(not mode & 0o222 for mode in modes.values()), modes
    assert modes["."] == 0o500  # mkdtemp's owner-only root is never widened
    assert modes["guardkit-player/AGENTS.md"] & 0o444

    # Turn 2: the live failure. The write fails inside the model's command.
    stray = profile / "full.log"
    second = _turn(
        repo,
        config,
        [("execute", {"command": f"scripts_check_output > {stray}; echo exit=$?"})],
    )
    assert not stray.exists()
    assert any("exit=" in output and "exit=0" not in output for output in _tool_outputs(second))

    # Turns 3 and 4 launch on the locked profile and do ordinary work.
    for index in (3, 4):
        _turn(
            repo,
            config,
            [("write_file", {"file_path": str(repo / f"made_{index}.py"), "content": "x = 1\n"})],
        )
        assert (repo / f"made_{index}.py").read_text() == "x = 1\n"
    assert _modes(profile) == modes


def test_a_profile_without_lock_profile_is_never_locked_and_a_stray_file_is_advice(
    tmp_path: Path, profile: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A supplied profile, or a new factory driven by an old GuardKit."""

    repo = _scaffold(tmp_path)
    config = _config(repo, profile, lock=False)
    assert config.lock_profile_identity is None
    stray = profile / "full.log"
    _turn(repo, config, [("execute", {"command": f"printf 'out' > {stray}"})])

    assert stray.read_text() == "out"
    assert all(_writable(profile / name) for name in ("", "guardkit-player"))
    with caplog.at_level("WARNING", logger="guardkitfactory.harness.dcode_harness"):
        _turn(repo, config, [])
    assert "full.log (file" in caplog.text


@pytest.mark.parametrize("lock", [True, False])
def test_parallel_launches_in_threads_all_succeed_locked_or_not(
    tmp_path: Path, profile: Path, lock: bool
) -> None:
    first = _scaffold(tmp_path, "first")
    _turn(first, _config(first, profile, lock=lock), [])
    assert _writable(profile) is not lock
    repos = [_scaffold(tmp_path, f"task-{index}") for index in range(4)]

    def run(repo: Path) -> bool:
        _turn(
            repo,
            _config(repo, profile, lock=lock),
            [("write_file", {"file_path": str(repo / "done.py"), "content": "ok = 1\n"})],
        )
        return (repo / "done.py").exists()

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(run, repos)) == [True] * 4
    assert _writable(profile) is not lock


@pytest.mark.parametrize("extra", ["file", "nested_file", "nonempty_memory", "link"])
def test_a_locked_profile_with_any_extra_content_is_named_and_the_turn_launches(
    tmp_path: Path, profile: Path, caplog: pytest.LogCaptureFixture, extra: str
) -> None:
    """The lock never hides content: anything beyond the clean shape is named."""

    repo = _scaffold(tmp_path)
    _turn(repo, _config(repo, profile, lock=True), [])
    agent = profile / "guardkit-player"
    target = {
        "file": profile / "extra.txt",
        "nested_file": agent / "skills" / "extra.md",
        "nonempty_memory": agent / "AGENTS.md",
        "link": agent / "linked",
    }[extra]
    # Something other than the factory unlocks one folder and writes there.
    parent = target.parent
    parent.chmod(0o700)
    if extra == "link":
        target.symlink_to(repo)
    elif extra == "nonempty_memory":
        target.chmod(0o600)
        target.write_text("remembered")
        target.chmod(0o400)
    else:
        target.write_text("extra")
    parent.chmod(0o500)
    assert not _writable(profile)

    with caplog.at_level("WARNING", logger="guardkitfactory.harness.dcode_harness"):
        _turn(repo, _config(repo, profile, lock=True), [])
    assert str(target.relative_to(profile)) in caplog.text


def _identity(path: Path) -> tuple[int, int]:
    status = path.lstat()
    return (status.st_dev, status.st_ino)


def _outside_tree(tmp_path: Path) -> tuple[Path, dict[str, int]]:
    """A writable directory outside the profile, shaped like a profile."""

    outside = tmp_path / "outside"
    (outside / "guardkit-player" / "skills").mkdir(parents=True)
    (outside / "guardkit-player" / "AGENTS.md").write_bytes(b"")
    return outside, _modes(outside)


def _skeleton(profile: Path) -> None:
    (profile / "guardkit-player" / "skills").mkdir(parents=True)
    (profile / "guardkit-player" / "AGENTS.md").write_bytes(b"")


def test_a_root_that_is_not_the_owners_directory_is_not_locked_and_not_changed(
    tmp_path: Path, profile: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from guardkitfactory.harness.dcode_harness import _lock_profile

    outside, before = _outside_tree(tmp_path)
    recorded = _identity(profile)
    link = tmp_path / "profile-link"
    link.symlink_to(outside, target_is_directory=True)

    with caplog.at_level("WARNING", logger="guardkitfactory.harness.dcode_harness"):
        _lock_profile(link, recorded)  # a link: not opened
        _lock_profile(outside, recorded)  # another directory: not the recorded one
    assert _modes(outside) == before
    messages = [r.getMessage() for r in caplog.records]
    assert any("without following a link" in m for m in messages)
    assert any("not the directory its owner made" in m for m in messages)


def test_an_agent_folder_replaced_by_a_link_is_not_locked_and_nothing_outside_changes(
    tmp_path: Path, profile: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from guardkitfactory.harness.dcode_harness import _lock_profile

    outside, before = _outside_tree(tmp_path)
    (profile / "guardkit-player").symlink_to(outside / "guardkit-player", target_is_directory=True)
    root_before = _modes(profile)["."]

    with caplog.at_level("WARNING", logger="guardkitfactory.harness.dcode_harness"):
        _lock_profile(profile, _identity(profile))
    assert "without following a link" in caplog.text
    assert _modes(outside) == before
    assert _modes(profile)["."] == root_before


@pytest.mark.parametrize(
    "extra",
    ["root_file", "agent_file", "skills_file", "nonempty_memory", "memory_link", "skills_link"],
)
def test_the_lock_leaves_anything_beyond_the_clean_shape_unlocked(
    tmp_path: Path, profile: Path, caplog: pytest.LogCaptureFixture, extra: str
) -> None:
    from guardkitfactory.harness.dcode_harness import _lock_profile

    outside, before = _outside_tree(tmp_path)
    _skeleton(profile)
    agent = profile / "guardkit-player"
    if extra == "root_file":
        (profile / "full.log").write_text("x")
    elif extra == "agent_file":
        (agent / "notes.json").write_text("{}")
    elif extra == "skills_file":
        (agent / "skills" / "SKILL.md").write_text("x")
    elif extra == "nonempty_memory":
        (agent / "AGENTS.md").write_text("remembered")
    elif extra == "memory_link":
        (agent / "AGENTS.md").unlink()
        (agent / "AGENTS.md").symlink_to(outside / "guardkit-player" / "AGENTS.md")
    else:
        (agent / "skills").rmdir()
        (agent / "skills").symlink_to(outside / "guardkit-player" / "skills")

    with caplog.at_level("WARNING", logger="guardkitfactory.harness.dcode_harness"):
        _lock_profile(profile, _identity(profile))
    assert "run profile not locked" in caplog.text
    assert _modes(outside) == before
    assert _writable(profile)


def test_the_lock_sets_exactly_the_clean_shape_read_only(profile: Path) -> None:
    from guardkitfactory.harness.dcode_harness import _lock_profile

    _skeleton(profile)
    _lock_profile(profile, _identity(profile))
    _lock_profile(profile, _identity(profile))  # a later launch: unchanged
    assert _modes(profile) == {
        ".": 0o500,
        "guardkit-player": 0o555,
        "guardkit-player/skills": 0o555,
        "guardkit-player/AGENTS.md": 0o444,
    }


def _locked_clean(profile: Path) -> bool:
    modes = _modes(profile)
    return set(modes) == {
        ".",
        "guardkit-player",
        "guardkit-player/skills",
        "guardkit-player/AGENTS.md",
    } and all(not mode & 0o222 for mode in modes.values())


def test_without_dcodes_agent_folder_nothing_is_made_or_locked(
    profile: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from guardkitfactory.harness.dcode_harness import _lock_profile

    with caplog.at_level("WARNING", logger="guardkitfactory.harness.dcode_harness"):
        _lock_profile(profile, _identity(profile))
    assert not any(profile.iterdir()) and _writable(profile)
    assert any("has not made guardkit-player" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("present", [(), ("skills",), ("AGENTS.md",)])
def test_missing_clean_entries_are_made_through_the_folder_and_locked(
    profile: Path, present: tuple[str, ...]
) -> None:
    from guardkitfactory.harness.dcode_harness import _lock_profile

    agent = profile / "guardkit-player"
    agent.mkdir()
    if "skills" in present:
        (agent / "skills").mkdir()
    if "AGENTS.md" in present:
        (agent / "AGENTS.md").write_bytes(b"")

    _lock_profile(profile, _identity(profile))

    assert _locked_clean(profile)
    assert (agent / "AGENTS.md").read_bytes() == b""


def test_launches_racing_to_make_the_clean_entries_all_lock_cleanly(profile: Path) -> None:
    import threading

    from guardkitfactory.harness.dcode_harness import _lock_profile

    (profile / "guardkit-player").mkdir()
    start = threading.Barrier(8)
    seen = _identity(profile)

    def lock(_index: int) -> None:
        start.wait(10)
        _lock_profile(profile, seen)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lock, range(8)))
    assert _locked_clean(profile)


def test_creating_through_the_folder_cannot_be_redirected(
    tmp_path: Path, profile: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """guardkit-player swapped for a link before the create: not locked, outside unchanged."""
    from guardkitfactory.harness.dcode_harness import _lock_profile

    outside = tmp_path / "outside-agent"
    outside.mkdir()
    before = _modes(outside)
    (profile / "guardkit-player").symlink_to(outside, target_is_directory=True)

    with caplog.at_level("WARNING", logger="guardkitfactory.harness.dcode_harness"):
        _lock_profile(profile, _identity(profile))
    assert "without following a link" in caplog.text
    assert _modes(outside) == before and not any(outside.iterdir())
    assert _writable(profile)


def _plain_config(repo: Path, profile: Path) -> Any:
    """A task with memory and skills both off (the live FEAT-05EE project)."""

    return build_player_config(
        cwd=repo, dcode_home=profile, lock_profile_identity=_identity(profile)
    )


def test_memory_off_first_task_is_locked_then_one_with_memory_launches(
    tmp_path: Path, profile: Path
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    _turn_plain(plain, profile)
    # dcode made only its folders; the lock made the empty AGENTS.md and locked.
    assert _locked_clean(profile)

    repo = _scaffold(tmp_path)
    _turn(repo, _config(repo, profile, lock=True), [])
    _turn_plain(plain, profile)
    assert _locked_clean(profile)


def test_memory_on_first_task_then_one_with_memory_off(tmp_path: Path, profile: Path) -> None:
    repo = _scaffold(tmp_path)
    _turn(repo, _config(repo, profile, lock=True), [])
    assert _locked_clean(profile)
    plain = tmp_path / "plain"
    plain.mkdir()
    _turn_plain(plain, profile)
    _turn(repo, _config(repo, profile, lock=True), [])
    assert _locked_clean(profile)


def test_feat_05ee_stray_write_in_the_memory_off_shape_fails_and_the_next_turn_launches(
    tmp_path: Path, profile: Path
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    _turn_plain(plain, profile)
    assert _locked_clean(profile)
    stray = profile / "full.log"
    exchange = _turn_plain(
        plain, profile, [("execute", {"command": f"printf 'check output' > {stray}; echo exit=$?"})]
    )
    assert not stray.exists()
    assert any("exit=" in out and "exit=0" not in out for out in _tool_outputs(exchange))
    _turn_plain(plain, profile)


def _turn_plain(
    repo: Path, profile: Path, calls: list[tuple[str, dict[str, object]]] | None = None
) -> Exchange:
    exchange = Exchange(calls or [])
    model, sync, async_ = _model(exchange)
    try:
        harness = LangGraphHarness(
            model, backend=_backend(repo), player_config=_plain_config(repo, profile)
        )
        events = asyncio.run(_collect(harness, repo))
        assert any(isinstance(event, ResultMessageEvent) for event in events)
        return exchange
    finally:
        _close_clients(sync, async_)


def test_concurrent_first_use_mixing_tasks_with_and_without_memory(
    tmp_path: Path, profile: Path
) -> None:
    assert not any(profile.iterdir()) and _writable(profile)
    plain = [tmp_path / f"plain-{index}" for index in range(2)]
    for repo in plain:
        repo.mkdir()
    full = [_scaffold(tmp_path, f"full-{index}") for index in range(2)]

    def run(job: tuple[str, Path]) -> bool:
        kind, repo = job
        if kind == "plain":
            _turn_plain(repo, profile)
        else:
            _turn(repo, _config(repo, profile, lock=True), [])
        return True

    jobs = [("plain", plain[0]), ("full", full[0]), ("plain", plain[1]), ("full", full[1])]
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(run, jobs)) == [True] * 4
    modes = _modes(profile)
    assert set(modes) == {
        ".",
        "guardkit-player",
        "guardkit-player/skills",
        "guardkit-player/AGENTS.md",
    }
    assert all(not mode & 0o222 for mode in modes.values()), modes
    _turn_plain(plain[0], profile)


def test_concurrent_first_use_of_a_fresh_profile_all_launch_and_lock_once(
    tmp_path: Path, profile: Path
) -> None:
    """N tasks start together on the empty, writable profile."""

    assert not any(profile.iterdir()) and _writable(profile)
    repos = [_scaffold(tmp_path, f"first-{index}") for index in range(4)]

    def run(repo: Path) -> bool:
        _turn(
            repo,
            _config(repo, profile, lock=True),
            [("write_file", {"file_path": str(repo / "done.py"), "content": "ok = 1\n"})],
        )
        return (repo / "done.py").exists()

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(run, repos)) == [True] * 4
    modes = _modes(profile)
    assert set(modes) == {
        ".",
        "guardkit-player",
        "guardkit-player/skills",
        "guardkit-player/AGENTS.md",
    }
    assert all(not mode & 0o222 for mode in modes.values()), modes
    # And a later turn still launches on it.
    _turn(repos[0], _config(repos[0], profile, lock=True), [])


def test_a_non_writable_profile_and_a_bad_lock_identity_are_advice(
    tmp_path: Path, profile: Path, caplog: pytest.LogCaptureFixture
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    profile.chmod(0o500)
    with caplog.at_level("INFO", logger="guardkitfactory.harness.player_config"):
        assert build_player_config(cwd=repo, dcode_home=profile).dcode_home == profile
    assert "is not writable" in caplog.text
    recorded = _identity(profile)
    assert (
        build_player_config(
            cwd=repo, dcode_home=profile, lock_profile_identity=recorded
        ).lock_profile_identity
        == recorded
    )
    for bad in (True, (1,), (1, "2"), (True, 1), [1, 2]):
        assert (
            build_player_config(
                cwd=repo, dcode_home=profile, lock_profile_identity=bad  # type: ignore[arg-type]
            ).lock_profile_identity
            is None
        )
