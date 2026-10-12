"""The code search runner against the real pinned programs.

Skipped, with the reason, unless ``GUARDKITFACTORY_CODE_SEARCH_DIR`` (or the
image's ``/opt/code-search/bin``) holds exactly the pinned executables: these
tests are about what the real programs do, so a stand-in would prove nothing.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

from guardkitfactory import code_search

_READY, _WHY = code_search.available()
pytestmark = pytest.mark.skipif(not _READY, reason=f"pinned programs not installed: {_WHY}")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"},
    ).stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src" / "users.py").write_text(
        "class UserStore:\n"
        "    def __init__(self):\n"
        "        self.users = {}\n"
        "\n"
        "    def deactivate(self, user_id):\n"
        "        self.users[user_id].active = False\n"
        "\n"
        "def count_active(store):\n"
        "    return sum(1 for u in store.users.values() if u.active)\n"
    )
    (root / "tests" / "test_users.py").write_text(
        "from src.users import UserStore, count_active\n"
        "\n"
        "def test_count_active_ignores_inactive():\n"
        "    assert count_active(UserStore()) == 0\n"
    )
    (root / "src" / "broken.py").write_text("def oops(:\n    return 1\n")
    (root / "notes.dart").write_text("int countActive() => 0;\n")
    (root / "schema.sql").write_text("CREATE TABLE users (id int, active bool);\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    return root


def _tree_state(root: Path) -> dict[str, tuple[int, int]]:
    state = {}
    for path in sorted(root.rglob("*")):
        if ".git" in path.relative_to(root).parts:
            continue
        st = path.lstat()
        state[str(path.relative_to(root))] = (st.st_size, st.st_mtime_ns)
    return state


# -- finding existing implementation and tests ---------------------------------


def test_ranked_search_finds_implementation_and_includes_tests(repo: Path) -> None:
    answer = code_search.run("search", repo, query="count active users")
    assert answer["status"] == "ok"
    paths = {r["path"] for r in answer["results"]}
    assert "src/users.py" in paths
    assert "tests/test_users.py" in paths  # Probe leaves tests out by default
    assert answer["coverage"]["tests_included"] is True
    block = next(r for r in answer["results"] if r["path"] == "src/users.py")
    assert block["first_line"] >= 1 and block["last_line"] >= block["first_line"]
    assert answer["tool"] == {"name": "probe", "version": "0.6.0-rc341"}
    assert answer["source"]["kind"] == "worktree"
    assert answer["source"]["head"] == _git(repo, "rev-parse", "HEAD")


def test_literal_and_regex_search_report_lines_and_coverage(repo: Path) -> None:
    literal = code_search.run("search", repo, query="count_active(", mode="literal")
    assert literal["status"] == "ok"
    assert {(r["path"], r["first_line"]) for r in literal["results"]} >= {
        ("src/users.py", 8),
        ("tests/test_users.py", 4),
    }
    assert literal["coverage"]["files_searched"] >= 4
    regex = code_search.run("search", repo, query=r"def \w+_active", mode="regex")
    assert regex["status"] == "ok"
    assert ("src/users.py", 8) in {(r["path"], r["first_line"]) for r in regex["results"]}
    # The same search keeps the same results in the same order every time.
    again = code_search.run("search", repo, query=r"def \w+_active", mode="regex")
    assert again["results"] == regex["results"]


def test_outline_lists_symbols_with_one_based_lines(repo: Path) -> None:
    answer = code_search.run("outline", repo, path="src/users.py")
    assert answer["status"] == "ok"
    names = {r["name"]: r for r in answer["results"]}
    assert names["UserStore"]["first_line"] == 1
    assert names["count_active"]["first_line"] == 8
    members = {m["name"] for m in names["UserStore"].get("members", [])}
    assert {"__init__", "deactivate"} <= members


def test_pattern_matches_structure(repo: Path) -> None:
    answer = code_search.run("pattern", repo, pattern="$X.active", language="python")
    assert answer["status"] == "ok"
    assert {r["path"] for r in answer["results"]} == {"src/users.py"}
    assert answer["coverage"]["files_scanned"] >= 1


# -- no matches is only said when the whole scope was searched ----------------


@pytest.mark.parametrize(
    ("operation", "kwargs"),
    [
        ("search", {"query": "zzqqnothinghere", "mode": "literal"}),
        ("search", {"query": "zzqqnothinghere", "mode": "regex"}),
        ("search", {"query": "zzqqnothinghere"}),
        ("pattern", {"pattern": "zzqq_nothing($A)", "language": "python"}),
    ],
)
def test_genuine_no_match(repo: Path, operation: str, kwargs: dict) -> None:
    answer = code_search.run(operation, repo, **kwargs)
    assert answer["status"] == "no_matches", answer
    assert answer["results"] == [] and answer["truncation"] == []


@pytest.mark.parametrize(
    "path", ["absent", "src/absent.py", "../outside", "/etc", "src/../../outside"]
)
def test_missing_or_outside_paths_are_input_errors(repo: Path, path: str) -> None:
    for operation, kwargs in (
        ("search", {"query": "x", "mode": "literal"}),
        ("search", {"query": "users"}),
        ("outline", {}),
        ("pattern", {"pattern": "$X", "language": "python"}),
    ):
        answer = code_search.run(operation, repo, path=path, **kwargs)
        assert answer["status"] == "input_error", (operation, path, answer)
        assert answer["results"] == []


def test_link_out_of_the_worktree_is_refused(repo: Path, tmp_path: Path) -> None:
    outside = tmp_path / "secret"
    outside.mkdir()
    (outside / "keys.txt").write_text("count_active\n")
    (repo / "escape").symlink_to(outside, target_is_directory=True)
    answer = code_search.run("search", repo, query="count_active", mode="literal",
                             path="escape")
    assert answer["status"] == "input_error"
    assert "outside" in answer["note"]


def test_unreadable_path_is_an_input_error(repo: Path) -> None:
    if os.geteuid() == 0:
        pytest.skip("root reads everything")
    locked = repo / "locked"
    locked.mkdir()
    (locked / "a.py").write_text("x = 1\n")
    locked.chmod(0)
    try:
        answer = code_search.run("search", repo, query="x", mode="literal", path="locked")
        assert answer["status"] == "input_error"
    finally:
        locked.chmod(0o755)


@pytest.mark.parametrize(
    "query", ["AND OR NOT", "and (", "!!! ??? ...", "   "]
)
def test_ranked_queries_without_words_are_input_errors(repo: Path, query: str) -> None:
    answer = code_search.run("search", repo, query=query)
    assert answer["status"] == "input_error"


def test_operator_words_never_reach_probe(repo: Path) -> None:
    assert code_search.query_words("count AND active OR (users NOT x") == [
        "count", "active", "users", "x",
    ]
    answer = code_search.run("search", repo, query="count AND (")
    assert answer["status"] == "ok"
    assert answer["query"]["words"] == ["count"]


def test_invalid_regex_and_pattern_are_input_errors(repo: Path) -> None:
    regex = code_search.run("search", repo, query="def (", mode="regex")
    assert regex["status"] == "input_error"
    pattern = code_search.run("pattern", repo, pattern="def $F(", language="python")
    assert pattern["status"] == "input_error"


def test_unsupported_languages_say_so(repo: Path) -> None:
    outline = code_search.run("outline", repo, path="notes.dart")
    assert outline["status"] == "unsupported"
    sql = code_search.run("outline", repo, path="schema.sql")
    assert sql["status"] == "unsupported"
    pattern = code_search.run("pattern", repo, pattern="$X", language="sql")
    assert pattern["status"] == "unsupported"
    # Text search still covers them.
    found = code_search.run("search", repo, query="countActive", mode="literal")
    assert found["status"] == "ok" and found["results"][0]["path"] == "notes.dart"


def test_malformed_source_does_not_break_anything(repo: Path) -> None:
    outline = code_search.run("outline", repo, path="src/broken.py")
    assert outline["status"] in ("ok", "no_matches")
    text = code_search.run("search", repo, query="oops", mode="literal")
    assert text["status"] == "ok" and text["results"][0]["path"] == "src/broken.py"
    assert "syntax errors" in code_search.capabilities()["not_diagnosed"]


# -- bounds --------------------------------------------------------------------


def test_result_count_and_character_caps_are_partial(repo: Path) -> None:
    many = repo / "many.py"
    many.write_text("".join(f"needle_{i} = {i}\n" for i in range(200)))
    capped = code_search.run("search", repo, query="needle_", mode="literal", max_results=5)
    assert capped["status"] == "partial"
    assert len(capped["results"]) == 5
    assert any("of 200" in reason for reason in capped["truncation"])
    small = code_search.run("search", repo, query="needle_", mode="literal",
                            max_results=50, max_chars=2_000)
    assert small["status"] == "partial"
    assert len(json.dumps(small)) <= 2_000
    assert any("characters" in reason for reason in small["truncation"])


def test_raw_output_cap_stops_the_program(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / "big.txt").write_text("hay\n" * 200_000)
    monkeypatch.setattr(code_search, "MAX_OUTPUT_BYTES", 4096)
    answer = code_search.run("search", repo, query="hay", mode="literal")
    assert answer["status"] == "partial"
    assert any("program output cut" in reason for reason in answer["truncation"])


def test_timeout_stops_the_program_and_is_partial(repo: Path) -> None:
    started = time.monotonic()
    answer = code_search.run("search", repo, query="(a+)+$", mode="regex", timeout_s=0.001)
    assert time.monotonic() - started < 10
    assert answer["status"] in ("partial", "ok", "no_matches")
    if answer["status"] == "partial":
        assert any("stopped after" in reason for reason in answer["truncation"])


def test_cancelled_task_stops_the_program_group(repo: Path, tmp_path: Path) -> None:
    """A slow stand-in program in place of rg proves the whole group is
    stopped; the pinned-tool check is bypassed only for this test."""

    slow = tmp_path / "bin"
    slow.mkdir()
    marker = tmp_path / "child.pid"
    script = slow / "rg"
    script.write_text(
        "#!/bin/sh\n"
        f"sleep 30 & echo $! > {marker}\n"
        "wait\n"
    )
    script.chmod(0o755)
    fake = {
        "dir": str(slow), "ok": True, "problems": [],
        "tools": {name: {"path": str(script), "version": t.version, "ok": True}
                  for name, t in code_search.PINNED_TOOLS.items()},
    }

    async def scenario() -> None:
        task = asyncio.ensure_future(
            code_search.run_async("search", repo, query="x", mode="literal", timeout_s=60)
        )
        for _ in range(200):
            if marker.exists() and marker.read_text().strip():
                break
            await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(code_search, "toolkit", lambda: fake)
        asyncio.run(scenario())
    child = int(marker.read_text().strip())
    time.sleep(0.2)
    # Gone, or a zombie waiting for a reaper (a container whose PID 1 does not
    # reap): either way it is no longer running.
    stat = Path(f"/proc/{child}/stat")
    assert not stat.exists() or stat.read_text().split(") ", 1)[1].startswith("Z")


def test_file_names_that_look_like_flags_stay_paths(repo: Path) -> None:
    flag = repo / "--rewrite=x"
    flag.mkdir()
    (flag / "inside.py").write_text("def flag_marker():\n    return 1\n")
    for operation, kwargs in (
        ("search", {"query": "flag marker"}),
        ("search", {"query": "flag_marker", "mode": "literal"}),
        ("outline", {}),
        ("pattern", {"pattern": "return $V", "language": "python"}),
    ):
        answer = code_search.run(operation, repo, path="--rewrite=x", **kwargs)
        assert answer["status"] == "ok", (operation, answer)
        assert all(r["path"].startswith("--rewrite=x/") for r in answer["results"])


def test_line_breaks_in_literal_queries_are_input_errors(repo: Path) -> None:
    answer = code_search.run("search", repo, query="a\nb", mode="literal")
    assert answer["status"] == "input_error"


def test_git_runs_without_any_user_or_system_configuration(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[list[str], dict[str, str]]] = []
    real = subprocess.run

    def spy(argv, *args, **kwargs):
        if argv and argv[0] == "git":
            seen.append((list(argv), dict(kwargs.get("env") or {})))
        return real(argv, *args, **kwargs)

    monkeypatch.setattr(code_search.subprocess, "run", spy)
    code_search.worktree_source(repo)
    assert seen
    for argv, env in seen:
        assert "core.fsmonitor=false" in argv
        assert env["HOME"] == "/nonexistent"
        assert env["GIT_CONFIG_GLOBAL"] == "/dev/null"
        assert env["GIT_CONFIG_NOSYSTEM"] == "1"


def test_cancel_event_before_start(repo: Path) -> None:
    cancel = threading.Event()
    cancel.set()
    answer = code_search.run("search", repo, query="x", mode="literal", cancel=cancel)
    assert answer["status"] == "cancelled"


# -- a changing worktree -------------------------------------------------------


def test_edits_additions_and_deletions_are_seen_next_call(repo: Path) -> None:
    (repo / "src" / "users.py").write_text("def renamed_marker():\n    return 1\n")
    (repo / "src" / "added.py").write_text("def added_marker():\n    return 2\n")
    (repo / "tests" / "test_users.py").unlink()
    edited = code_search.run("search", repo, query="renamed_marker", mode="literal")
    added = code_search.run("outline", repo, path="src/added.py")
    deleted = code_search.run("search", repo, query="count_active", mode="literal")
    assert edited["status"] == "ok"
    assert added["status"] == "ok" and added["results"][0]["name"] == "added_marker"
    assert deleted["status"] == "no_matches"
    source = deleted["source"]
    assert source["changed"] >= 1 and source["untracked"] == 1 and source["deleted"] == 1


def test_untracked_but_not_ignored_files_are_searched(repo: Path) -> None:
    (repo / ".gitignore").write_text("ignored/\n")
    (repo / "ignored").mkdir()
    (repo / "ignored" / "x.py").write_text("untracked_marker = 1\n")
    (repo / "fresh.py").write_text("untracked_marker = 2\n")
    answer = code_search.run("search", repo, query="untracked_marker", mode="literal")
    assert [r["path"] for r in answer["results"]] == ["fresh.py"]


def test_two_divergent_worktrees_see_only_their_own_files(repo: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    _git(repo, "worktree", "add", "-q", "-b", "other", str(other))
    (repo / "src" / "users.py").write_text("def only_in_main():\n    pass\n")
    (other / "src" / "users.py").write_text("def only_in_other():\n    pass\n")
    main_answer = code_search.run("search", repo, query="only_in", mode="literal")
    other_answer = code_search.run("search", other, query="only_in", mode="literal")
    assert [r["text"] for r in main_answer["results"]] == ["def only_in_main():"]
    assert [r["text"] for r in other_answer["results"]] == ["def only_in_other():"]
    assert main_answer["source"]["root"] != other_answer["source"]["root"]
    assert main_answer["source"]["fingerprint"] != other_answer["source"]["fingerprint"]


def test_same_status_different_contents_differ_in_fingerprint(
    repo: Path, tmp_path: Path
) -> None:
    other = tmp_path / "twin"
    _git(repo, "worktree", "add", "-q", "--detach", str(other))
    (repo / "src" / "users.py").write_text("x = 1\n")
    (other / "src" / "users.py").write_text("x = 2\n")
    first = code_search.worktree_source(repo)
    second = code_search.worktree_source(other)
    assert first["head"] == second["head"]
    assert first["changed"] == second["changed"] == 1
    assert first["fingerprint"] != second["fingerprint"]


def test_repeated_edits_to_an_untracked_file_change_the_fingerprint(repo: Path) -> None:
    scratch = repo / "scratch.py"
    scratch.write_text("a = 1\n")
    before = code_search.worktree_source(repo)["fingerprint"]
    scratch.write_text("a = 2\n")
    after = code_search.worktree_source(repo)["fingerprint"]
    assert before != after


def test_change_during_a_query_is_partial(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real = code_search._execute

    def edit_while_running(*args, **kwargs):
        result = real(*args, **kwargs)
        (repo / "src" / "users.py").write_text("changed = True\n")
        return result

    monkeypatch.setattr(code_search, "_execute", edit_while_running)
    answer = code_search.run("search", repo, query="count_active", mode="literal")
    assert answer["status"] == "partial"
    assert "the worktree changed while it was searched" in answer["truncation"]


def test_no_writes_to_the_tree_or_home(repo: Path, tmp_path: Path,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    before = _tree_state(repo)
    for operation, kwargs in (
        ("search", {"query": "count active"}),
        ("search", {"query": "count", "mode": "literal"}),
        ("search", {"query": "count", "mode": "regex"}),
        ("outline", {}),
        ("pattern", {"pattern": "$X.active", "language": "python"}),
    ):
        code_search.run(operation, repo, **kwargs)
    assert _tree_state(repo) == before
    assert list(home.iterdir()) == []


# -- a commit snapshot ---------------------------------------------------------


def test_snapshot_omission_inside_the_path_makes_no_match_partial(repo: Path) -> None:
    source = {"kind": "commit", "commit": "0" * 40, "omitted_count": 1}
    omitted = [{"path": "src/huge.py", "reason": "larger than the file size limit"}]
    inside = code_search.run("search", repo, query="zzqq", mode="literal", source=source,
                             omitted=omitted, respect_ignore=False)
    assert inside["status"] == "partial" and inside["results"] == []
    assert inside["source"] == source  # the list is used, not copied into the answer
    elsewhere = code_search.run("search", repo, query="zzqq", mode="literal", path="tests",
                                source=source, omitted=omitted, respect_ignore=False)
    assert elsewhere["status"] == "no_matches"


def test_a_long_omitted_list_never_crowds_out_results(repo: Path) -> None:
    omitted = [{"path": f"vendor/f{i}.py", "reason": "beyond the path limit"}
               for i in range(5_000)]
    answer = code_search.run("search", repo, query="count_active", mode="literal",
                             source={"kind": "commit", "omitted_count": 5_000},
                             omitted=omitted, respect_ignore=False, max_chars=4_000)
    assert answer["results"] and answer["status"] == "partial"


def test_self_check_passes() -> None:
    lines: list[str] = []
    assert code_search.self_check(lines.append) == 0
    assert json.loads(lines[0])["ok"] is True


def test_wrong_binary_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "bin"
    folder.mkdir()
    for tool in code_search.PINNED_TOOLS.values():
        fake = folder / tool.executable
        fake.write_text("#!/bin/sh\necho fake\n")
        fake.chmod(0o755)
    monkeypatch.setenv(code_search.TOOL_DIR_ENV, str(folder))
    ok, reason = code_search.available()
    assert not ok and "not the pinned" in reason
    answer = code_search.run("search", tmp_path, query="x", mode="literal")
    assert answer["status"] == "tool_unavailable"
