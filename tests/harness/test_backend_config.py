"""Integration tests for the AutoBuild backend + permissions factories (TASK-HMIG-002R).

Covers the four falsifier dimensions from the parent task:

(a) Positive tool flow — ``ls`` / ``read`` / ``write`` / ``edit`` / ``glob``
    / ``grep`` / ``execute`` all succeed inside a fixture worktree.
(b) Permission denial — :func:`build_autobuild_permissions` blocks writes
    to ``.git/``, ``.guardkit/state_transitions.json``,
    ``.guardkit/autobuild/*/coach_*.json`` and ``tasks/**``.
(c) ``execute`` timeout — the configured 600-second ceiling is wired
    through (verified by attribute + a fast behavioural check with a short
    override timeout).
(d) Traversal block — ``read("../../../etc/passwd")`` is rejected by
    ``virtual_mode=True``.

Plus AC-007: both factories are importable from the package root.

The deny-rule checks evaluate each :class:`FilesystemPermission` rule the
same way the deepagents permission middleware does (declaration-order,
first-match-wins, ``wcmatch`` with ``BRACE | GLOBSTAR``) rather than
spinning up a stub LLM. The check function exists privately in the
deepagents source tree but moved between 0.5.x and 0.6.x, so we
re-implement the tiny evaluator here against the **public**
``FilesystemPermission`` dataclass and the **public** ``wcmatch`` API. The
behaviour we're verifying is the *rules*; the deepagents middleware itself
is the library's own contract.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

import pytest
import wcmatch.glob as wcglob
from deepagents import FilesystemPermission
from deepagents.backends.composite import CompositeBackend
from deepagents.backends.local_shell import LocalShellBackend

from guardkitfactory import build_autobuild_backend, build_autobuild_permissions
from guardkitfactory.harness.backend_config import PathConfinedBackend, shell_home

def _git_checkout(path: Path) -> Path:
    """A plain git checkout (no network, no commit), like a build's worktree."""
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


# ---------------------------------------------------------------------------
# Local rule evaluator — see module docstring for why this is hand-rolled.
# ---------------------------------------------------------------------------

_FS_WCMATCH_FLAGS = wcglob.BRACE | wcglob.GLOBSTAR


def _evaluate_rules(
    rules: list[FilesystemPermission],
    operation: Literal["read", "write"],
    path: str,
) -> Literal["allow", "deny"]:
    """Mirror of deepagents' internal rule evaluator using only public API."""
    for rule in rules:
        if operation not in rule.operations:
            continue
        if any(
            wcglob.globmatch(path, pattern, flags=_FS_WCMATCH_FLAGS)
            for pattern in rule.paths
        ):
            return rule.mode
    return "allow"

# ---------------------------------------------------------------------------
# Factory return-shape — AC-001 / AC-002
# ---------------------------------------------------------------------------


def test_build_autobuild_backend_returns_composite_wrapping_localshellbackend(
    tmp_path: Path,
) -> None:
    """TASK-HMIG-002R-SUMM-ROOT (2026-06-04): return shape is CompositeBackend.

    The composite wrapper carries an ``artifacts_root`` that deepagents'
    summarisation middleware reads to compute its offload prefix. Its only
    routes are the two model-artifact folders (14 October 2026); it is a
    transparent pass-through for every other operation — the underlying
    ``LocalShellBackend`` still owns the on-disk behaviour. See
    ``backend_config.py`` module docstring for the chain.
    """
    backend = build_autobuild_backend(tmp_path)
    assert isinstance(backend, CompositeBackend)
    # TASK-FIX-WTESCAPE01: the composite default is now the write-confinement
    # wrapper; the LocalShellBackend still owns the on-disk behaviour one
    # level down and every non-write attribute delegates through.
    assert isinstance(backend.default, PathConfinedBackend)
    assert isinstance(backend.default._inner, LocalShellBackend)
    assert set(backend.routes) == {
        f"{backend.artifacts_root}/conversation_history/",
        f"{backend.artifacts_root}/large_tool_results/",
    }


def test_build_autobuild_backend_artifacts_root_is_outside_the_worktree(
    tmp_path: Path,
) -> None:
    """TASK-HMIG-002R-SUMM-ROOT, moved out of the worktree 14 October 2026.

    Without an ``artifacts_root``, deepagents' summarisation middleware falls
    back to ``"/"`` and computes ``/conversation_history`` as the offload
    prefix — which under NOVMODE's ``virtual_mode=False`` resolves to host
    root (read-only) and crashes the offload. With the worktree as the
    root, GuardKit's checkpoint commit took the transcripts into the build's
    branch. The root is now a real, private folder outside the project.
    """
    worktree = _git_checkout(tmp_path / "wt")
    backend = build_autobuild_backend(worktree)
    root = Path(backend.artifacts_root)
    assert root == (worktree / ".git" / "guardkit-scratch" / "model-artifacts").resolve()
    assert root.is_dir() and not root.is_symlink()
    assert (root.stat().st_mode & 0o777) == 0o700


def test_build_autobuild_backend_uses_worktree_as_root(tmp_path: Path) -> None:
    backend = build_autobuild_backend(tmp_path)
    assert backend.default.cwd == tmp_path.resolve()


def test_build_autobuild_backend_disables_virtual_mode(tmp_path: Path) -> None:
    """TASK-HMIG-002R-NOVMODE (2026-06-03): virtual_mode flipped to False.

    The Coach LLM is fed absolute filesystem paths by guardkit's
    orchestrator prompt. Under virtual_mode=True those paths were being
    silently rewritten into worktree-nested twins (see backend_config.py
    docstring and docs/reviews/autobuild-migration/TASK-FIX-A7D3-run-5.md).
    """
    backend = build_autobuild_backend(tmp_path)
    assert backend.default.virtual_mode is False


def test_build_autobuild_backend_configures_execute_timeout_to_600(
    tmp_path: Path,
) -> None:
    backend = build_autobuild_backend(tmp_path)
    # Private attribute name matches deepagents 0.5.x. If the upstream
    # rename happens, the visible failure here is preferable to silently
    # losing the 600 s ceiling. See AC-002.
    assert backend.default._default_timeout == 600


def test_build_autobuild_backend_configures_max_output_bytes_to_1mb(
    tmp_path: Path,
) -> None:
    backend = build_autobuild_backend(tmp_path)
    assert backend.default._max_output_bytes == 1_000_000


def test_build_autobuild_backend_env_contains_minimum_keys(tmp_path: Path) -> None:
    backend = build_autobuild_backend(tmp_path)
    assert backend.default._env["PATH"] == "/usr/bin:/bin"
    # 19 October 2026: HOME is private and outside the project.
    home = Path(backend.default._env["HOME"])
    assert home.is_dir()
    assert not home.is_relative_to(tmp_path.resolve())
    assert backend.default._env["TMPDIR"] == str(tmp_path / ".tmp")
    assert backend.default._env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert backend.default._env["PYTHONNOUSERSITE"] == "1"


def test_execute_python_imports_do_not_write_bytecode_or_inherit_ambient_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree = tmp_path / "project with spaces"
    worktree.mkdir()
    fixture = worktree / "private_fixture.py"
    fixture.write_text("VALUE = 'private-fixture-loaded'\n")
    project_python = worktree / ".venv" / "bin" / "python"
    project_python.parent.mkdir(parents=True)
    project_python.symlink_to(Path(sys.executable))
    monkeypatch.setenv("AUTOBUILD_AMBIENT_SENTINEL", "must-not-leak")
    backend = build_autobuild_backend(worktree)

    command = (
        "{python} -c \"import os, private_fixture; "
        "print(private_fixture.VALUE); "
        "print(os.environ.get('AUTOBUILD_AMBIENT_SENTINEL', 'absent')); "
        "print(os.environ['PYTHONDONTWRITEBYTECODE']); "
        "print(os.environ['PYTHONNOUSERSITE'])\""
    )
    for python in ("python3", ".venv/bin/python"):
        result = backend.execute(command.format(python=python))
        assert result.exit_code == 0, result.output
        assert result.output.splitlines() == [
            "private-fixture-loaded",
            "absent",
            "1",
            "1",
        ]

    assert not (worktree / "__pycache__").exists()


def test_build_autobuild_backend_creates_private_tmpdir_and_mktemp_works(
    tmp_path: Path,
) -> None:
    temp_directory = tmp_path / ".tmp"
    assert not temp_directory.exists()

    backend = build_autobuild_backend(tmp_path)

    assert temp_directory.is_dir()
    assert temp_directory.stat().st_mode & 0o077 == 0
    result = backend.execute("mktemp -d")
    assert result.exit_code == 0
    created = Path(result.output.strip())
    assert created.is_dir()
    assert created.parent == temp_directory


def test_build_autobuild_backend_preserves_existing_tmpdir(
    tmp_path: Path,
) -> None:
    temp_directory = tmp_path / ".tmp"
    temp_directory.mkdir(mode=0o751)
    temp_directory.chmod(0o751)
    marker = temp_directory / "keep.txt"
    marker.write_text("keep\n")
    original_mode = temp_directory.stat().st_mode

    backend = build_autobuild_backend(tmp_path)

    assert backend.default._env["TMPDIR"] == str(temp_directory)
    assert marker.read_text() == "keep\n"
    assert temp_directory.stat().st_mode == original_mode


def test_build_autobuild_backend_refuses_tmpdir_file(tmp_path: Path) -> None:
    (tmp_path / ".tmp").write_text("not a directory\n")

    with pytest.raises(ValueError, match="TMPDIR must be a directory"):
        build_autobuild_backend(tmp_path)


@pytest.mark.parametrize("broken", [False, True], ids=["existing-target", "broken"])
def test_build_autobuild_backend_refuses_tmpdir_symlink(
    tmp_path: Path, broken: bool
) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    target = tmp_path / "redirected"
    if not broken:
        target.mkdir()
    (worktree / ".tmp").symlink_to(target, target_is_directory=True)

    with pytest.raises(ValueError, match="TMPDIR must not be a symlink"):
        build_autobuild_backend(worktree)


def test_build_autobuild_backend_refuses_tmpdir_creation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    temp_directory = tmp_path / ".tmp"
    original_mkdir = Path.mkdir

    def fail_tmpdir(path: Path, *args, **kwargs):
        if path == temp_directory:
            raise PermissionError("synthetic refusal")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_tmpdir)
    with pytest.raises(ValueError, match="TMPDIR could not be created"):
        build_autobuild_backend(tmp_path)


def test_build_autobuild_backend_refuses_missing_worktree(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="TMPDIR could not be created"):
        build_autobuild_backend(tmp_path / "missing-worktree")




def test_build_autobuild_backend_env_does_not_inherit_operator_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Set a sentinel env var that we'd expect to leak under inherit_env=True.
    monkeypatch.setenv("AUTOBUILD_FACTORY_LEAK_SENTINEL", "leaked")
    backend = build_autobuild_backend(tmp_path)
    assert "AUTOBUILD_FACTORY_LEAK_SENTINEL" not in backend.default._env


def test_build_autobuild_backend_picks_up_worktree_venv_pythonpath(
    tmp_path: Path,
) -> None:
    venv_site = tmp_path / ".venv" / "lib" / "python3.12" / "site-packages"
    venv_site.mkdir(parents=True)
    backend = build_autobuild_backend(tmp_path)
    assert backend.default._env["PYTHONPATH"] == str(venv_site)


def test_build_autobuild_backend_omits_pythonpath_when_no_venv(
    tmp_path: Path,
) -> None:
    backend = build_autobuild_backend(tmp_path)
    assert "PYTHONPATH" not in backend.default._env


# ---------------------------------------------------------------------------
# TASK-HMIG-002R-SUMM-ROOT regression — the offload path the
# summarisation middleware computes must land inside the worktree, not at
# host root. See ``autobuild-FEAT-AOF-run-2.md`` lines 342-350 for the
# observed failure (``[Errno 30] Read-only file system: '/conversation_history'``).
# ---------------------------------------------------------------------------


def test_summarization_offload_path_lands_outside_the_worktree(tmp_path: Path) -> None:
    """The model's offload writes succeed, and land outside the worktree.

    Reproduces the paths the SDK middleware computes:
    ``f"{artifacts_root.rstrip('/')}/conversation_history/<thread>.md"`` and
    ``.../large_tool_results/<id>``. Before SUMM-ROOT, ``artifacts_root``
    defaulted to ``"/"`` and the write went to host root; until 14 October
    2026 it went into the worktree, and a checkpoint commit took it into a
    public project's branch. Each write must succeed (the write fence lets
    it through), land in the private folder, and leave the worktree clean.
    """
    worktree = _git_checkout(tmp_path / "wt")
    backend = build_autobuild_backend(worktree)
    root = backend.artifacts_root.rstrip("/")
    private = worktree.resolve() / ".git" / "guardkit-scratch" / "model-artifacts"

    for target, content, expected in (
        (f"{root}/conversation_history/session_abc.md", "# offloaded turn 1\n",
         private / "conversation_history" / "session_abc.md"),
        (f"{root}/large_tool_results/call_1", "LARGE\n",
         private / "large_tool_results" / "call_1"),
    ):
        result = backend.write(target, content)
        assert result.error is None, f"offload write rejected: {result.error!r}"
        assert expected.read_text() == content
        # The model reads the offloaded file back by the same path.
        read = backend.read(target)
        assert read.error is None, read.error
        assert content.strip() in read.file_data["content"]
    # The middleware appends to the transcript with ``edit``.
    edited = backend.edit(
        f"{root}/conversation_history/session_abc.md",
        "# offloaded turn 1\n",
        "# offloaded turn 1\n# turn 2\n",
    )
    assert edited.error is None, edited.error

    for name in ("conversation_history", "large_tool_results"):
        assert not (worktree / name).exists()
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=worktree, check=True, capture_output=True, text=True,
    ).stdout
    assert "conversation_history" not in status
    assert "large_tool_results" not in status


def test_linked_worktree_artifacts_live_in_its_own_git_directory(
    tmp_path: Path,
) -> None:
    """A linked worktree (how GuardKit builds) uses ``.git/worktrees/<name>``."""
    main = _git_checkout(tmp_path / "main")
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "base"],
        cwd=main, check=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"},
    )
    linked = tmp_path / "linked"
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "feature", str(linked)],
        cwd=main, check=True,
    )
    backend = build_autobuild_backend(linked)
    root = Path(backend.artifacts_root)
    assert root == (
        main / ".git" / "worktrees" / "linked" / "guardkit-scratch" / "model-artifacts"
    ).resolve()
    assert not root.is_relative_to(linked.resolve())


def test_a_non_git_worktree_gets_a_private_temporary_folder(tmp_path: Path) -> None:
    """No git directory: still never inside the worktree, and still writable."""
    backend = build_autobuild_backend(tmp_path)
    root = Path(backend.artifacts_root)
    assert not root.is_relative_to(tmp_path.resolve())
    assert (root.stat().st_mode & 0o777) == 0o700
    result = backend.write(f"{root}/conversation_history/s.md", "x\n")
    assert result.error is None, result.error
    assert not (tmp_path / "conversation_history").exists()


def test_a_symlinked_model_artifacts_folder_is_refused(tmp_path: Path) -> None:
    worktree = _git_checkout(tmp_path / "wt")
    scratch = worktree / ".git" / "guardkit-scratch"
    scratch.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (scratch / "model-artifacts").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        build_autobuild_backend(worktree)


def test_read_only_backend_gets_no_artifact_routes(tmp_path: Path) -> None:
    """A read-only backend refuses the offload writes, as before."""
    worktree = _git_checkout(tmp_path / "wt")
    backend = build_autobuild_backend(worktree, read_only=True)
    assert backend.routes == {}
    root = backend.artifacts_root.rstrip("/")
    result = backend.write(f"{root}/conversation_history/s.md", "x\n")
    assert result.error is not None
    assert not (worktree / "conversation_history").exists()


def test_existing_open_artifact_folders_are_made_owner_only(tmp_path: Path) -> None:
    """Folders left at 0755 (an older run, a hand-made folder) become 0700.

    And the offload and the read-back still work afterwards.
    """
    worktree = _git_checkout(tmp_path / "wt")
    private = worktree / ".git" / "guardkit-scratch" / "model-artifacts"
    for folder in (
        private,
        private / "conversation_history",
        private / "large_tool_results",
    ):
        folder.mkdir(parents=True, exist_ok=True)
        folder.chmod(0o755)

    backend = build_autobuild_backend(worktree)

    for folder in (
        private,
        private / "conversation_history",
        private / "large_tool_results",
    ):
        assert (folder.stat().st_mode & 0o777) == 0o700, folder
    target = f"{backend.artifacts_root}/conversation_history/session_abc.md"
    assert backend.write(target, "# offloaded\n").error is None
    read = backend.read(target)
    assert read.error is None and "offloaded" in read.file_data["content"]
    # And again on the next use: a folder opened up between runs is closed.
    private.chmod(0o755)
    build_autobuild_backend(worktree)
    assert (private.stat().st_mode & 0o777) == 0o700


def test_an_artifact_folder_owned_by_another_user_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree = _git_checkout(tmp_path / "wt")
    private = worktree / ".git" / "guardkit-scratch" / "model-artifacts"
    private.mkdir(parents=True)
    real_uid = os.geteuid()
    monkeypatch.setattr(os, "geteuid", lambda: real_uid + 1)
    with pytest.raises(ValueError, match="another user"):
        build_autobuild_backend(worktree)


def test_concurrent_backends_for_one_new_worktree_share_one_folder(
    tmp_path: Path,
) -> None:
    """Eight builds at once for a fresh worktree all succeed, same folder.

    Before the fix the losers of the ``mkdir`` race failed construction (or,
    in GuardKit's scratch folder, fell back to a temporary folder).
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor

    for round_number in range(10):
        worktree = _git_checkout(tmp_path / f"wt{round_number}")
        start = threading.Barrier(8)

        def build() -> str:
            start.wait()
            return build_autobuild_backend(worktree).artifacts_root

        with ThreadPoolExecutor(max_workers=8) as pool:
            roots = list(pool.map(lambda _: build(), range(8)))
        expected = (
            worktree / ".git" / "guardkit-scratch" / "model-artifacts"
        ).resolve()
        assert set(roots) == {str(expected)}, roots


def test_temporary_artifact_folders_are_removed_at_exit(tmp_path: Path) -> None:
    from guardkitfactory.harness import backend_config

    backend = build_autobuild_backend(tmp_path)
    root = Path(backend.artifacts_root)
    assert root.is_dir()
    backend_config._remove_temporary_model_artifacts()
    assert not root.exists()


def test_summarization_offload_does_not_attempt_host_root_write(
    tmp_path: Path,
) -> None:
    """Defensive: the prefix used by the SDK must not start with bare ``/``.

    A regression that resets ``artifacts_root`` back to ``"/"`` would
    silently start trying to write to host root again. We don't trigger an
    actual write here (we'd need superuser to attempt it on most systems);
    we just check the prefix shape.
    """
    backend = build_autobuild_backend(tmp_path)
    prefix = f"{backend.artifacts_root.rstrip('/')}/conversation_history"
    assert prefix != "/conversation_history", (
        "TASK-HMIG-002R-SUMM-ROOT regression — offload prefix collapsed back "
        "to bare host root. Check that build_autobuild_backend still wraps "
        "the LocalShellBackend in a CompositeBackend with artifacts_root set "
        "to the worktree."
    )
    assert not prefix.startswith(str(tmp_path.resolve())), (
        f"offload prefix {prefix!r} is inside the worktree {tmp_path.resolve()!r}"
    )


# ---------------------------------------------------------------------------
# (a) Positive tool flow — falsifier dimension (a)
#
# TASK-HMIG-002R-NOVMODE (2026-06-03): these tests now use real absolute
# paths under tmp_path rather than virtual paths rooted at "/". The flip
# from virtual_mode=True to virtual_mode=False means "/sample.txt" would
# target the real OS root rather than <tmp_path>/sample.txt. The tool
# contract we want to verify is "absolute paths the orchestrator hands the
# LLM are interpreted literally" — that's exactly what these tests now
# exercise.
# ---------------------------------------------------------------------------


def test_positive_tool_flow_write_then_read_round_trips(tmp_path: Path) -> None:
    backend = build_autobuild_backend(tmp_path)
    sample = str(tmp_path / "sample.txt")
    write_result = backend.write(sample, "hello world\n")
    assert write_result.error is None

    read_result = backend.read(sample)
    assert read_result.error is None
    assert read_result.file_data is not None
    assert read_result.file_data["content"] == "hello world\n"


def test_positive_tool_flow_ls_lists_written_file(tmp_path: Path) -> None:
    backend = build_autobuild_backend(tmp_path)
    sample = str(tmp_path / "sample.txt")
    backend.write(sample, "hello\n")
    ls_result = backend.ls(str(tmp_path))
    assert ls_result.error is None
    assert ls_result.entries is not None
    assert any(entry["path"] == sample for entry in ls_result.entries)


def test_positive_tool_flow_glob_matches_written_file(tmp_path: Path) -> None:
    backend = build_autobuild_backend(tmp_path)
    sample = str(tmp_path / "sample.txt")
    backend.write(sample, "hello\n")
    # glob patterns remain relative to root_dir even with virtual_mode=False.
    # Match by basename to stay portable across macOS /var → /private/var
    # symlink resolution in the returned absolute paths.
    glob_result = backend.glob("**/*.txt")
    assert glob_result.error is None
    assert glob_result.matches is not None
    assert any(m["path"].endswith("/sample.txt") for m in glob_result.matches)


def test_positive_tool_flow_grep_finds_content_in_written_file(
    tmp_path: Path,
) -> None:
    backend = build_autobuild_backend(tmp_path)
    sample = str(tmp_path / "sample.txt")
    backend.write(sample, "hello world\n")
    grep_result = backend.grep("hello", path=str(tmp_path))
    assert grep_result.error is None
    assert grep_result.matches is not None
    assert len(grep_result.matches) >= 1


def test_positive_tool_flow_edit_replaces_existing_content(tmp_path: Path) -> None:
    backend = build_autobuild_backend(tmp_path)
    sample = str(tmp_path / "sample.txt")
    backend.write(sample, "hello world\n")
    edit_result = backend.edit(sample, "world", "there")
    assert edit_result.error is None
    assert edit_result.occurrences == 1

    read_result = backend.read(sample)
    assert read_result.file_data is not None
    assert read_result.file_data["content"] == "hello there\n"


def test_positive_tool_flow_execute_returns_zero_for_simple_command(
    tmp_path: Path,
) -> None:
    backend = build_autobuild_backend(tmp_path)
    result = backend.execute("echo done")
    assert result.exit_code == 0
    assert "done" in result.output


def test_absolute_path_no_longer_doubled_under_worktree(tmp_path: Path) -> None:
    """TASK-HMIG-002R-NOVMODE regression — the run-5 failure mode.

    Before the flip, ``write(absolute_path_inside_tmp_path, ...)`` under
    ``virtual_mode=True`` would create the file at
    ``<tmp_path>/<absolute_path_string>`` (doubly nested). With
    ``virtual_mode=False`` the absolute path must land at the absolute
    path literally. See ``docs/reviews/autobuild-migration/TASK-FIX-A7D3-run-5.md``.
    """
    backend = build_autobuild_backend(tmp_path)
    nested = tmp_path / "a" / "b" / "coach_turn_1.json"
    nested.parent.mkdir(parents=True)
    backend.write(str(nested), '{"decision": "accept"}')

    # The file must exist at the absolute path we asked for.
    assert nested.is_file()
    # And NOT at the doubly-nested path the virtual_mode=True bug produced.
    doubled = tmp_path / str(nested).lstrip("/")
    assert not doubled.exists(), (
        f"virtual_mode regression: file landed at the doubled path {doubled}"
    )


# ---------------------------------------------------------------------------
# (b) Permission denial — falsifier dimension (b)
#
# TASK-HMIG-002R-NOPERMS (2026-06-03): the deny-rule body tests below are
# skipped because ``build_autobuild_permissions()`` currently returns ``[]``
# pending DeepAgents upstream support for permissions on execute-capable
# backends (issue #2894, closed/declined — see permissions.py docstring).
#
# The single regression test
# ``test_build_autobuild_permissions_is_empty_until_upstream_lands_or_custom_middleware_ships``
# (AC-004) replaces the previous "list is not empty" assertion. When
# restoring, unskip the rule-body tests and delete the regression test.
# ---------------------------------------------------------------------------


def test_build_autobuild_permissions_is_empty_until_upstream_lands_or_custom_middleware_ships(
) -> None:
    """AC-004 regression — catches accidental restoration before upstream catches up.

    See ``src/guardkitfactory/harness/permissions.py`` docstring and
    ``TASK-HMIG-002R-PERMS-CUSTOM-MIDDLEWARE`` for the restore path.
    """
    assert build_autobuild_permissions() == []


_NOPERMS_SKIP_REASON = (
    "TASK-HMIG-002R-NOPERMS — build_autobuild_permissions() returns [] until "
    "DeepAgents upstream supports permissions on execute-capable backends "
    "(#2894 declined) or TASK-HMIG-002R-PERMS-CUSTOM-MIDDLEWARE ships an "
    "in-tree custom middleware. See permissions.py docstring for restore."
)


@pytest.mark.skip(reason=_NOPERMS_SKIP_REASON)
def test_build_autobuild_permissions_targets_write_operations() -> None:
    perms = build_autobuild_permissions()
    for perm in perms:
        assert "write" in perm.operations
        assert perm.mode == "deny"


@pytest.mark.skip(reason=_NOPERMS_SKIP_REASON)
def test_permissions_deny_writes_to_dot_git_inside_worktree() -> None:
    perms = build_autobuild_permissions()
    assert _evaluate_rules(perms, "write", "/tmp/wt-xyz/.git/HEAD") == "deny"
    assert (
        _evaluate_rules(perms, "write", "/tmp/wt/.git/refs/heads/main") == "deny"
    )


@pytest.mark.skip(reason=_NOPERMS_SKIP_REASON)
def test_permissions_deny_writes_to_state_transitions_json() -> None:
    perms = build_autobuild_permissions()
    assert (
        _evaluate_rules(
            perms, "write", "/tmp/wt/.guardkit/state_transitions.json"
        )
        == "deny"
    )


@pytest.mark.skip(reason=_NOPERMS_SKIP_REASON)
def test_permissions_deny_writes_to_coach_verdict_files() -> None:
    perms = build_autobuild_permissions()
    assert (
        _evaluate_rules(
            perms,
            "write",
            "/tmp/wt/.guardkit/autobuild/TASK-001/coach_verdict.json",
        )
        == "deny"
    )


@pytest.mark.skip(reason=_NOPERMS_SKIP_REASON)
def test_permissions_deny_writes_inside_tasks_tree() -> None:
    perms = build_autobuild_permissions()
    assert _evaluate_rules(perms, "write", "/tmp/wt/tasks/TASK-001.md") == "deny"
    assert (
        _evaluate_rules(
            perms, "write", "/tmp/wt/tasks/in_progress/TASK-002.md"
        )
        == "deny"
    )


@pytest.mark.skip(reason=_NOPERMS_SKIP_REASON)
def test_permissions_allow_writes_to_normal_source_paths() -> None:
    perms = build_autobuild_permissions()
    assert (
        _evaluate_rules(perms, "write", "/tmp/wt/src/foo.py") == "allow"
    )
    assert (
        _evaluate_rules(perms, "write", "/tmp/wt/tests/test_foo.py") == "allow"
    )


@pytest.mark.skip(reason=_NOPERMS_SKIP_REASON)
def test_permissions_allow_reads_under_denied_paths() -> None:
    # Reads remain permissive even where writes are denied — the rule
    # operations list only covers "write". See the permissions module
    # docstring for rationale (integrity, not confidentiality).
    perms = build_autobuild_permissions()
    assert _evaluate_rules(perms, "read", "/tmp/wt/.git/HEAD") == "allow"
    assert (
        _evaluate_rules(perms, "read", "/tmp/wt/tasks/TASK-001.md") == "allow"
    )


# ---------------------------------------------------------------------------
# (c) ``execute`` timeout enforcement — falsifier dimension (c)
# ---------------------------------------------------------------------------


def test_execute_honours_per_call_timeout_override(tmp_path: Path) -> None:
    # The factory default is 600 s. We verify the timeout *mechanism* with a
    # 1-second per-call override to keep the test fast. The 600 s default
    # itself is verified above via the attribute assertion (test name
    # ``..._configures_execute_timeout_to_600``).
    backend = build_autobuild_backend(tmp_path)
    started = time.monotonic()
    result = backend.execute("sleep 5", timeout=1)
    elapsed = time.monotonic() - started
    # 124 is the standard ``timeout(1)`` exit code on Unix.
    assert result.exit_code == 124
    assert elapsed < 3.0, f"sleep with timeout=1 took {elapsed:.2f}s"


def test_execute_honours_per_call_timeout_override_when_gather_capped(
    tmp_path: Path,
) -> None:
    """TASK-FIX-WTESCAPE01 review regression — timeout through the wrappers.

    ``execute_accepts_timeout`` introspects the CLASS-level ``execute``
    signature of ``CompositeBackend.default``. With ``max_tool_result_chars``
    set the default is a ``TruncatingBackend``; its former ``*args, **kwargs``
    signature hid the ``timeout`` name, so ``CompositeBackend.execute``
    silently dropped per-call overrides on the Coach-gather path.
    """
    backend = build_autobuild_backend(tmp_path, max_tool_result_chars=4096)
    started = time.monotonic()
    result = backend.execute("sleep 5", timeout=1)
    elapsed = time.monotonic() - started
    assert result.exit_code == 124
    assert elapsed < 3.0, f"sleep with timeout=1 took {elapsed:.2f}s"


# ---------------------------------------------------------------------------
# (d) Traversal block — falsifier dimension (d)
#
# TASK-HMIG-002R-NOVMODE (2026-06-03): the original falsifier-(d) was
# delivered by virtual_mode=True's path-confinement layer, which we
# deliberately flipped off. Upstream's docs already noted virtual_mode
# "provides NO security with shell access enabled" — the SDK harness we're
# migrating away from never had this protection either (acceptEdits +
# cwd=worktree does not sandbox path resolution). The test is preserved
# as a skip so the behavioural change is visible in test output and to
# anchor the restore conversation if AutoBuild's threat model later moves
# to multi-tenant (which would call for swapping LocalShellBackend for a
# real sandbox per parent review D-11, not for re-enabling virtual_mode).
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason=(
        "TASK-HMIG-002R-NOVMODE — virtual_mode=False intentionally removes "
        "the path-confinement layer that rejected ../../../etc/passwd at "
        "the backend boundary. See backend_config.py docstring and "
        "docs/reviews/autobuild-migration/TASK-FIX-A7D3-run-5.md for "
        "rationale (Coach LLM was fed absolute paths and they were being "
        "rewritten into doubly-nested worktree-relative paths)."
    )
)
def test_traversal_above_worktree_is_blocked(tmp_path: Path) -> None:
    backend = build_autobuild_backend(tmp_path)
    with pytest.raises(ValueError, match="traversal"):
        backend.read("../../../etc/passwd")


# ---------------------------------------------------------------------------
# AC-007 — package-root exposure
# ---------------------------------------------------------------------------


def test_factories_exposed_at_guardkitfactory_package_root() -> None:
    import guardkitfactory

    assert hasattr(guardkitfactory, "build_autobuild_backend")
    assert hasattr(guardkitfactory, "build_autobuild_permissions")
    assert "build_autobuild_backend" in guardkitfactory.__all__
    assert "build_autobuild_permissions" in guardkitfactory.__all__


# ---------------------------------------------------------------------------
# TASK-FIX-WTESCAPE01 — write confinement (worktree escape via absolute paths)
#
# FEAT-C332 run 2 (2026-06-12): the Player wrote to absolute host-repo paths
# fed in by task context, and NOVMODE's ``virtual_mode=False`` honoured them
# literally. ``PathConfinedBackend`` restores containment for write/edit
# (sync + async) while preserving literal absolute paths INSIDE the worktree
# (the Coach-JSON semantics NOVMODE exists for).
# ---------------------------------------------------------------------------


def _make_worktree(tmp_path: Path) -> Path:
    """Create a worktree dir nested like ``.guardkit/worktrees/FEAT-X``."""
    worktree = tmp_path / "host" / ".guardkit" / "worktrees" / "FEAT-X"
    worktree.mkdir(parents=True)
    return worktree


class TestWriteConfinement:
    """AC-001 — absolute/traversal writes outside the worktree are rejected."""

    def test_absolute_write_outside_worktree_is_rejected(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)
        victim = tmp_path / "host" / "guardkit" / "agent_invoker.py"
        backend = build_autobuild_backend(worktree)

        result = backend.write(str(victim), "stray player edit")

        assert result.error is not None
        assert "outside the worktree" in result.error
        assert not victim.exists()

    def test_absolute_edit_outside_worktree_is_rejected(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)
        victim = tmp_path / "host" / "guardkit" / "coach_validator.py"
        victim.parent.mkdir(parents=True)
        victim.write_text("original = True\n")
        backend = build_autobuild_backend(worktree)

        result = backend.edit(str(victim), "original = True", "original = False")

        assert result.error is not None
        assert "outside the worktree" in result.error
        assert victim.read_text() == "original = True\n"

    def test_relative_traversal_write_is_rejected(self, tmp_path: Path) -> None:
        worktree = _make_worktree(tmp_path)
        backend = build_autobuild_backend(worktree)

        result = backend.write("../../../escape.txt", "stray")

        assert result.error is not None
        assert not (tmp_path / "host" / "escape.txt").exists()

    def test_symlink_inside_worktree_cannot_smuggle_write_out(
        self, tmp_path: Path
    ) -> None:
        """``Path.resolve()`` judges the write by where it actually lands."""
        worktree = _make_worktree(tmp_path)
        outside = tmp_path / "host" / "elsewhere"
        outside.mkdir(parents=True)
        (worktree / "innocent").symlink_to(outside)
        backend = build_autobuild_backend(worktree)

        result = backend.write(str(worktree / "innocent" / "stray.txt"), "x")

        assert result.error is not None
        assert not (outside / "stray.txt").exists()

    def test_absolute_write_inside_worktree_still_works(
        self, tmp_path: Path
    ) -> None:
        """NOVMODE preservation: in-worktree absolute paths resolve literally.

        This is the Coach-JSON write path that motivated
        ``virtual_mode=False`` — confinement must not regress it.
        """
        worktree = _make_worktree(tmp_path)
        target = worktree / ".guardkit" / "autobuild" / "T1" / "coach_turn_1.json"
        backend = build_autobuild_backend(worktree)

        result = backend.write(str(target), "{}")

        assert result.error is None
        assert target.read_text() == "{}"

    def test_relative_write_inside_worktree_still_works(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)
        backend = build_autobuild_backend(worktree)

        result = backend.write("src/new_module.py", "x = 1\n")

        assert result.error is None
        assert (worktree / "src" / "new_module.py").read_text() == "x = 1\n"

    def test_async_write_and_edit_are_confined(self, tmp_path: Path) -> None:
        """The a-variants must not bypass confinement via ``__getattr__``."""
        import asyncio

        worktree = _make_worktree(tmp_path)
        victim = tmp_path / "host" / "stray_async.txt"
        backend = build_autobuild_backend(worktree)

        write_result = asyncio.run(backend.default.awrite(str(victim), "stray"))
        edit_result = asyncio.run(
            backend.default.aedit(str(victim), "stray", "edited")
        )

        assert write_result.error is not None
        assert edit_result.error is not None
        assert not victim.exists()


class TestSymlinkPolicy:
    """AC-002 — the ``guardkitfactory`` sibling symlink is explicitly allowed;
    any other sibling symlink is not."""

    def test_guardkitfactory_sibling_symlink_target_is_writable(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)
        factory_repo = tmp_path / "guardkitfactory_checkout"
        factory_repo.mkdir()
        (worktree.parent / "guardkitfactory").symlink_to(factory_repo)
        backend = build_autobuild_backend(worktree)

        # Through the symlink path…
        via_symlink = backend.write(
            str(worktree.parent / "guardkitfactory" / "via_symlink.txt"), "ok"
        )
        # …and via the resolved target directly.
        direct = backend.write(str(factory_repo / "direct.txt"), "ok")

        assert via_symlink.error is None
        assert direct.error is None
        assert (factory_repo / "via_symlink.txt").exists()
        assert (factory_repo / "direct.txt").exists()

    def test_other_sibling_symlinks_are_not_allowed(self, tmp_path: Path) -> None:
        worktree = _make_worktree(tmp_path)
        other_repo = tmp_path / "some_other_repo"
        other_repo.mkdir()
        (worktree.parent / "otherproject").symlink_to(other_repo)
        backend = build_autobuild_backend(worktree)

        result = backend.write(
            str(worktree.parent / "otherproject" / "stray.txt"), "x"
        )

        assert result.error is not None
        assert not (other_repo / "stray.txt").exists()

    def test_extra_write_roots_param_allows_explicit_roots(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)
        sibling = tmp_path / "explicit_sibling"
        sibling.mkdir()
        backend = build_autobuild_backend(worktree, extra_write_roots=[sibling])

        result = backend.write(str(sibling / "allowed.txt"), "ok")

        assert result.error is None
        assert (sibling / "allowed.txt").read_text() == "ok"


class TestScratchFolder:
    """3 October 2026: a scratch folder outside the project for throwaway
    scripts. Before it, a builder's ``/tmp`` script was refused and the
    builder put it inside the worktree, where it counted as project work."""

    def _scratch(self, tmp_path: Path) -> Path:
        # Where guardkit puts it: inside the worktree's git directory.
        git_dir = tmp_path / "host" / ".git" / "worktrees" / "FEAT-X"
        git_dir.mkdir(parents=True)
        return git_dir / "guardkit-scratch"

    def test_scratch_folder_is_created_and_writable(self, tmp_path: Path) -> None:
        worktree = _make_worktree(tmp_path)
        scratch = self._scratch(tmp_path)
        backend = build_autobuild_backend(worktree, scratch_root=scratch)

        result = backend.write(str(scratch / "verify.py"), "print('ok')\n")

        assert result.error is None
        assert (scratch / "verify.py").read_text() == "print('ok')\n"
        assert backend.delete(str(scratch / "verify.py")).error is None
        # The folder itself cannot be deleted, like any allowed root.
        assert backend.delete(str(scratch)).error is not None

    def test_refusal_names_the_scratch_folder(self, tmp_path: Path) -> None:
        worktree = _make_worktree(tmp_path)
        scratch = self._scratch(tmp_path)
        backend = build_autobuild_backend(worktree, scratch_root=scratch)

        result = backend.write("/tmp/verify_e592_002.py", "x")

        assert result.error is not None
        assert "outside the worktree" in result.error
        assert f"use the scratch folder '{scratch.resolve()}'" in result.error

    def test_traversal_escaping_both_roots_is_still_refused(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)
        scratch = self._scratch(tmp_path)
        backend = build_autobuild_backend(worktree, scratch_root=scratch)

        result = backend.write(str(scratch / ".." / "config"), "x")
        result_relative = backend.write("../../../escape.txt", "x")

        assert result.error is not None
        assert result_relative.error is not None
        assert not (scratch.parent / "config").exists()
        assert not (tmp_path / "host" / "escape.txt").exists()

    def test_symlinked_scratch_folder_is_skipped_not_followed(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)
        scratch = self._scratch(tmp_path)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        scratch.symlink_to(elsewhere)

        backend = build_autobuild_backend(worktree, scratch_root=scratch)
        result = backend.write(str(scratch / "verify.py"), "x")

        assert result.error is not None
        assert not (elsewhere / "verify.py").exists()
        assert "scratch folder" not in result.error
        assert backend.default.scratch_root is None

    def test_scratch_folder_inside_the_project_is_skipped(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)
        inside = worktree / "src"
        inside.mkdir()

        backend = build_autobuild_backend(worktree, scratch_root=inside)

        assert backend.default.scratch_root is None
        assert "scratch folder" not in backend.write("/tmp/x.py", "x").error
        # Nothing is created inside the project either.
        build_autobuild_backend(worktree, scratch_root=inside / "guardkit-scratch")
        assert not (inside / "guardkit-scratch").exists()

    def test_accepted_scratch_folder_is_reported(self, tmp_path: Path) -> None:
        worktree = _make_worktree(tmp_path)
        scratch = self._scratch(tmp_path)

        backend = build_autobuild_backend(
            worktree, scratch_root=scratch, max_tool_result_chars=1000
        )

        # Readable through the optional truncating wrapper too.
        assert backend.default.scratch_root == scratch.resolve()

    def test_without_a_scratch_folder_the_refusal_is_unchanged(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)
        backend = build_autobuild_backend(worktree)

        result = backend.write("/tmp/verify.py", "x")

        assert result.error is not None
        assert result.error.endswith("Retry with a worktree-relative path.")


class TestEscapeObservability:
    """AC-004 — escaped-write attempts surface as WARNINGs in the turn log."""

    def test_rejected_write_logs_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        worktree = _make_worktree(tmp_path)
        backend = build_autobuild_backend(worktree)

        with caplog.at_level(
            logging.WARNING, logger="guardkitfactory.harness.backend_config"
        ):
            backend.write(str(tmp_path / "host" / "stray.txt"), "x")

        assert any(
            "write confinement" in record.message
            and record.levelno == logging.WARNING
            for record in caplog.records
        )


class TestHostRepoStaysClean:
    """AC-003 — a host git repo is untouched by write/edit attempts using
    absolute host paths (the recorded-fixture form of the integration test)."""

    def test_host_git_status_clean_after_escape_attempts(
        self, tmp_path: Path
    ) -> None:
        import subprocess

        host = tmp_path / "host"
        host.mkdir()
        tracked = host / "guardkit" / "orchestrator" / "coach_evidence.py"
        tracked.parent.mkdir(parents=True)
        tracked.write_text("EVIDENCE = 'pristine'\n")
        subprocess.run(["git", "init", "-q", str(host)], check=True)
        subprocess.run(["git", "-C", str(host), "add", "-A"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(host),
                "-c",
                "user.email=t@t",
                "-c",
                "user.name=t",
                "commit",
                "-qm",
                "baseline",
            ],
            check=True,
        )

        worktree = host / ".guardkit" / "worktrees" / "FEAT-X"
        worktree.mkdir(parents=True)
        backend = build_autobuild_backend(worktree)

        # The FEAT-C332 run-2 shapes: edit a tracked host file by absolute
        # path, write a brand-new host file by absolute path.
        edit_result = backend.edit(
            str(tracked), "EVIDENCE = 'pristine'", "EVIDENCE = 'poisoned'"
        )
        write_result = backend.write(
            str(host / "guardkit" / "orchestrator" / "stray_new.py"), "x = 1\n"
        )

        status = subprocess.run(
            ["git", "-C", str(host), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        assert edit_result.error is not None
        assert write_result.error is not None
        assert status == ""
        assert tracked.read_text() == "EVIDENCE = 'pristine'\n"


# ---------------------------------------------------------------------------
# Deep Agents 0.7 delete surface and generic declared-path protection
# ---------------------------------------------------------------------------


class TestDeleteConfinement:
    def test_delete_existing_file_inside_worktree(self, tmp_path: Path) -> None:
        worktree = _make_worktree(tmp_path)
        victim = worktree / "src" / "obsolete.py"
        victim.parent.mkdir()
        victim.write_text("obsolete = True\n")
        backend = build_autobuild_backend(worktree)

        result = backend.delete(str(victim))

        assert result.error is None
        assert result.path == str(victim)
        assert not victim.exists()

    def test_async_delete_existing_file_inside_worktree(self, tmp_path: Path) -> None:
        import asyncio

        worktree = _make_worktree(tmp_path)
        victim = worktree / "obsolete.txt"
        victim.write_text("old\n")
        backend = build_autobuild_backend(worktree)

        result = asyncio.run(backend.adelete(str(victim)))

        assert result.error is None
        assert not victim.exists()

    @pytest.mark.parametrize("async_mode", [False, True])
    @pytest.mark.parametrize("relative", [False, True])
    def test_delete_cyclic_symlink_returns_error_without_mutation(
        self, tmp_path: Path, async_mode: bool, relative: bool
    ) -> None:
        import asyncio

        worktree = _make_worktree(tmp_path)
        loop = worktree / "loop"
        loop.symlink_to("loop")
        backend = build_autobuild_backend(worktree)
        path = "loop" if relative else str(loop)

        result = (
            asyncio.run(backend.adelete(path)) if async_mode else backend.delete(path)
        )

        assert result.error
        assert loop.is_symlink()
        assert loop.readlink() == Path("loop")

    @pytest.mark.parametrize("async_mode", [False, True])
    @pytest.mark.parametrize("error_type", [OSError, RuntimeError])
    @pytest.mark.parametrize("fail_on", [1, 2])
    def test_delete_resolution_failure_never_reaches_inner_backend(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        async_mode: bool,
        error_type: type[Exception],
        fail_on: int,
    ) -> None:
        import asyncio
        from unittest.mock import patch

        worktree = _make_worktree(tmp_path)
        victim = worktree / "keep.txt"
        victim.write_text("keep\n")
        backend = build_autobuild_backend(worktree)
        original_resolve = Path.resolve
        attempts = 0

        def failing_resolve(path: Path, *args: object, **kwargs: object) -> Path:
            nonlocal attempts
            if path == victim:
                attempts += 1
                if attempts == fail_on:
                    raise error_type("Cannot resolve deletion target")
            return original_resolve(path, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", failing_resolve)
        method = "adelete" if async_mode else "delete"
        with patch.object(backend.default._inner, method) as inner_delete:
            result = (
                asyncio.run(backend.adelete(str(victim)))
                if async_mode else backend.delete(str(victim))
            )
            inner_delete.assert_not_called()

        assert result.error
        assert "Cannot resolve deletion target" in result.error
        assert victim.read_text() == "keep\n"

    def test_absolute_delete_outside_worktree_is_rejected(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)
        victim = tmp_path / "host" / "guardkit" / "keep.py"
        victim.parent.mkdir(parents=True)
        victim.write_text("keep = True\n")
        backend = build_autobuild_backend(worktree)

        result = backend.delete(str(victim))

        assert result.error is not None
        assert "outside the worktree" in result.error
        assert victim.read_text() == "keep = True\n"

    def test_relative_traversal_delete_is_rejected(self, tmp_path: Path) -> None:
        worktree = _make_worktree(tmp_path)
        victim = tmp_path / "host" / "keep.txt"
        victim.write_text("keep\n")
        backend = build_autobuild_backend(worktree)

        result = backend.delete("../../../keep.txt")

        assert result.error is not None
        assert victim.exists()

    def test_symlink_escape_delete_is_rejected(self, tmp_path: Path) -> None:
        worktree = _make_worktree(tmp_path)
        outside = tmp_path / "outside"
        outside.mkdir()
        victim = outside / "keep.txt"
        victim.write_text("keep\n")
        link = worktree / "outside-link"
        link.symlink_to(outside)
        backend = build_autobuild_backend(worktree)

        result = backend.delete(str(link / "keep.txt"))

        assert result.error is not None
        assert victim.exists()

    def test_delete_inside_permitted_extra_root(self, tmp_path: Path) -> None:
        worktree = _make_worktree(tmp_path)
        extra = tmp_path / "explicit-extra"
        extra.mkdir()
        victim = extra / "generated.txt"
        victim.write_text("generated\n")
        backend = build_autobuild_backend(worktree, extra_write_roots=[extra])

        result = backend.delete(str(victim))

        assert result.error is None
        assert not victim.exists()

    def test_delete_allowed_root_itself_is_rejected(self, tmp_path: Path) -> None:
        worktree = _make_worktree(tmp_path)
        backend = build_autobuild_backend(worktree)

        result = backend.delete(str(worktree))

        assert result.error is not None
        assert "allowed root" in result.error
        assert worktree.is_dir()

    def test_delete_available_through_gather_wrapper(self, tmp_path: Path) -> None:
        worktree = _make_worktree(tmp_path)
        victim = worktree / "gather.tmp"
        victim.write_text("temporary\n")
        backend = build_autobuild_backend(
            worktree, max_tool_result_chars=1024
        )

        result = backend.delete(str(victim))

        assert result.error is None
        assert not victim.exists()


class TestDeclaredPathProtection:
    def test_declared_non_python_file_cannot_be_overwritten_edited_or_deleted(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)
        evidence = worktree / "checks" / "contracts" / "expected.json"
        evidence.parent.mkdir(parents=True)
        evidence.write_text('{"expected": "independent"}\n')
        backend = build_autobuild_backend(
            worktree, protected_paths=["checks/contracts/expected.json"]
        )

        overwrite = backend.write(str(evidence), '{"expected": "weakened"}\n')
        edit = backend.edit(str(evidence), "independent", "weakened")
        delete = backend.delete(str(evidence))

        assert overwrite.error is not None
        assert edit.error is not None
        assert delete.error is not None
        assert evidence.read_text() == '{"expected": "independent"}\n'

    def test_declared_directory_protects_existing_and_new_descendants(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)
        evidence_dir = worktree / "verification" / "oracles"
        evidence_dir.mkdir(parents=True)
        existing = evidence_dir / "baseline.snap"
        existing.write_text("independent\n")
        backend = build_autobuild_backend(
            worktree, protected_paths=["verification/oracles"]
        )

        new_file = evidence_dir / "new.snap"
        assert backend.write(str(existing), "weakened\n").error is not None
        assert backend.write(str(new_file), "new\n").error is not None
        assert backend.delete(str(evidence_dir)).error is not None
        assert existing.read_text() == "independent\n"
        assert not new_file.exists()

    def test_symlinked_declared_directory_is_protected_by_alias_and_target(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)
        shared = worktree / "oracle_data"
        shared.mkdir()
        oracle = shared / "expected.txt"
        oracle.write_text("independent\n")
        declared = worktree / "verification"
        declared.symlink_to(shared, target_is_directory=True)
        backend = build_autobuild_backend(
            worktree, protected_paths=["verification"]
        )

        assert backend.write(str(declared / oracle.name), "weakened\n").error is not None
        assert backend.edit(str(oracle), "independent", "weakened").error is not None
        assert backend.delete(str(declared)).error is not None
        assert oracle.read_text() == "independent\n"
        assert declared.is_symlink()

    def test_absent_declaration_adds_no_stack_or_path_defaults(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)
        arbitrary = worktree / "web" / "generated" / "snapshot.txt"
        arbitrary.parent.mkdir(parents=True)
        arbitrary.write_text("before\n")
        backend = build_autobuild_backend(worktree)

        result = backend.write(str(arbitrary), "after\n")

        assert result.error is None
        assert arbitrary.read_text() == "after\n"

    def test_missing_or_escaping_declaration_fails_construction(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)
        outside = tmp_path / "outside"
        outside.mkdir()

        with pytest.raises(ValueError, match="does not exist"):
            build_autobuild_backend(worktree, protected_paths=["missing"])
        with pytest.raises(ValueError, match="escapes the worktree"):
            build_autobuild_backend(worktree, protected_paths=[outside])


class TestLaunchEnvironment:
    """12 October 2026: the project's ``launch:`` names reach the shell.

    The shell does not inherit this process's environment. Its ``HOME`` was
    the worktree until 19 October 2026 (it is now private, outside the
    project), so a tool cache landed in the project unless the project
    declared a scratch folder for it. The project declares settings to carry
    over and scratch folders for its caches; the backend applies exactly what
    is declared and knows no tool.
    """

    def _scratch(self, tmp_path: Path) -> Path:
        git_dir = tmp_path / "host" / ".git" / "worktrees" / "FEAT-X"
        git_dir.mkdir(parents=True)
        return git_dir / "guardkit-scratch"

    def test_no_declaration_leaves_the_env_identical(self, tmp_path: Path) -> None:
        worktree = _make_worktree(tmp_path)
        scratch = self._scratch(tmp_path)

        plain = build_autobuild_backend(worktree, scratch_root=scratch)
        declared_none = build_autobuild_backend(
            worktree, scratch_root=scratch, launch_environment=None
        )

        assert declared_none.default._env == plain.default._env
        # Exactly the environment the shell had before launch declarations.
        assert plain.default._env == {
            "PATH": "/usr/bin:/bin",
            "HOME": str(shell_home(worktree)),
            "TMPDIR": str(worktree / ".tmp"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        }
        assert not (scratch / "toolchain").exists()

    def test_scratch_names_resolve_under_the_scratch_folder(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)
        scratch = self._scratch(tmp_path)

        backend = build_autobuild_backend(
            worktree,
            scratch_root=scratch,
            launch_environment={"scratch": ["TOOL_CACHE", "TOOL_HOME"]},
        )

        env = backend.default._env
        for name in ("TOOL_CACHE", "TOOL_HOME"):
            folder = scratch.resolve() / "toolchain" / name
            assert env[name] == str(folder)
            assert folder.is_dir()
            assert (folder.stat().st_mode & 0o777) == 0o700
        # HOME stays the shell's own private folder, outside the project.
        assert env["HOME"] == str(shell_home(worktree))
        assert not Path(env["HOME"]).is_relative_to(worktree.resolve())

    def test_settings_pass_through_only_when_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        worktree = _make_worktree(tmp_path)
        monkeypatch.setenv("BROWSERS_AT", "/opt/browsers")
        monkeypatch.delenv("NOT_SET_HERE", raising=False)

        backend = build_autobuild_backend(
            worktree,
            launch_environment={"settings": ["BROWSERS_AT", "NOT_SET_HERE"]},
        )

        env = backend.default._env
        assert env["BROWSERS_AT"] == "/opt/browsers"
        assert "NOT_SET_HERE" not in env

    def test_a_setting_never_replaces_the_backends_own(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        worktree = _make_worktree(tmp_path)
        monkeypatch.setenv("PYTHONNOUSERSITE", "0")

        backend = build_autobuild_backend(
            worktree, launch_environment={"settings": ["PYTHONNOUSERSITE"]}
        )

        assert backend.default._env["PYTHONNOUSERSITE"] == "1"

    def test_declared_scratch_without_a_scratch_folder_fails(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)

        with pytest.raises(ValueError, match="no scratch folder"):
            build_autobuild_backend(
                worktree, launch_environment={"scratch": ["TOOL_CACHE"]}
            )
        assert list(worktree.iterdir()) == []

    def test_declared_scratch_with_a_refused_scratch_folder_fails(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)
        inside = worktree / "src"
        inside.mkdir()

        with pytest.raises(ValueError, match="inside the project"):
            build_autobuild_backend(
                worktree,
                scratch_root=inside / "guardkit-scratch",
                launch_environment={"scratch": ["TOOL_CACHE"]},
            )
        assert not (inside / "guardkit-scratch").exists()

    def test_malformed_names_fail(self, tmp_path: Path) -> None:
        worktree = _make_worktree(tmp_path)
        scratch = self._scratch(tmp_path)

        with pytest.raises(ValueError, match="is not a variable name"):
            build_autobuild_backend(
                worktree, launch_environment={"settings": ["1BAD"]}
            )
        with pytest.raises(ValueError, match="unknown keys"):
            build_autobuild_backend(
                worktree, launch_environment={"pass_through": ["X"]}
            )
        with pytest.raises(ValueError, match="set by the backend itself"):
            build_autobuild_backend(
                worktree,
                scratch_root=scratch,
                launch_environment={"scratch": ["PYTHONNOUSERSITE"]},
            )

    @pytest.mark.parametrize(
        "name",
        ["PATH", "SSH_AUTH_SOCK", "GUARDKIT_X", "forge_x", "OPENAI_API_BASE",
         "REGISTRY_TOKEN", "db_password", "X" * 129],
    )
    def test_reserved_and_credential_shaped_names_fail(
        self, tmp_path: Path, name: str
    ) -> None:
        worktree = _make_worktree(tmp_path)
        scratch = self._scratch(tmp_path)

        for key in ("settings", "scratch"):
            with pytest.raises(ValueError, match="AutoBuild launch"):
                build_autobuild_backend(
                    worktree,
                    scratch_root=scratch,
                    launch_environment={key: [name]},
                )

    def test_a_name_with_a_trailing_newline_fails(self, tmp_path: Path) -> None:
        worktree = _make_worktree(tmp_path)

        with pytest.raises(ValueError, match="is not a variable name"):
            build_autobuild_backend(
                worktree, launch_environment={"settings": ["GOCACHE\n"]}
            )

    @pytest.mark.parametrize("raw", ["GOCACHE", {"GOCACHE": 1}, 3])
    def test_names_that_are_not_a_list_fail(self, tmp_path: Path, raw) -> None:
        worktree = _make_worktree(tmp_path)
        scratch = self._scratch(tmp_path)

        for key in ("settings", "scratch"):
            with pytest.raises(ValueError, match="must be a list of names"):
                build_autobuild_backend(
                    worktree,
                    scratch_root=scratch,
                    launch_environment={key: raw},
                )

    def test_launch_scratch_root_places_names_without_write_access(
        self, tmp_path: Path
    ) -> None:
        """The Coach's shell: names resolve under the handed-over folder, and
        its file tools still cannot write there."""
        worktree = _make_worktree(tmp_path)
        scratch = self._scratch(tmp_path)

        backend = build_autobuild_backend(
            worktree,
            launch_environment={"scratch": ["TOOL_CACHE"]},
            launch_scratch_root=scratch,
        )

        folder = scratch.resolve() / "toolchain" / "TOOL_CACHE"
        assert backend.default._env["TOOL_CACHE"] == str(folder)
        assert folder.is_dir()
        assert backend.default.scratch_root is None
        refused = backend.write(str(folder / "x.txt"), "x")
        assert refused.error is not None
        assert not (folder / "x.txt").exists()
        # The shell itself can still fill its cache.
        assert backend.execute('echo c > "$TOOL_CACHE/c"').exit_code == 0
        assert (folder / "c").read_text() == "c\n"

    def test_launch_scratch_root_inside_the_project_fails(
        self, tmp_path: Path
    ) -> None:
        worktree = _make_worktree(tmp_path)

        with pytest.raises(ValueError, match="inside the project"):
            build_autobuild_backend(
                worktree,
                launch_environment={"scratch": ["TOOL_CACHE"]},
                launch_scratch_root=worktree / "cache",
            )
        assert not (worktree / "cache").exists()

    def test_launch_scratch_root_alone_changes_nothing(self, tmp_path: Path) -> None:
        worktree = _make_worktree(tmp_path)
        scratch = self._scratch(tmp_path)

        plain = build_autobuild_backend(worktree)
        handed = build_autobuild_backend(worktree, launch_scratch_root=scratch)

        assert handed.default._env == plain.default._env
        assert not scratch.exists()

    def test_real_go_and_npm_use_the_declared_folders(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The real shell, with host toolchains when present (skipped if not).

        ``go env`` and ``npm cache verify`` report the scratch folders, and
        the worktree gains no files. ``XDG_CONFIG_HOME`` (Go's telemetry
        folder) and ``NODE_COMPILE_CACHE`` are declared because without them
        go and node write under the worktree ``HOME`` and ``TMPDIR``.
        """
        import shutil

        go = shutil.which("go")
        node = shutil.which("node")
        npm = shutil.which("npm")
        if go is None or node is None or npm is None:
            pytest.skip("go, node or npm is not on this machine's PATH")
        npm_cli = Path(npm).resolve()
        worktree = _make_worktree(tmp_path)
        scratch = self._scratch(tmp_path)
        # Keeps go from fetching another toolchain; also proves a declared
        # setting reaches the real shell.
        monkeypatch.setenv("GOTOOLCHAIN", "local")
        backend = build_autobuild_backend(
            worktree,
            scratch_root=scratch,
            launch_environment={
                "settings": ["GOTOOLCHAIN"],
                "scratch": [
                    "GOPATH",
                    "GOCACHE",
                    "npm_config_cache",
                    "XDG_CONFIG_HOME",
                    "NODE_COMPILE_CACHE",
                ],
            },
        )
        before = sorted(str(p.relative_to(worktree)) for p in worktree.rglob("*"))

        go_env = backend.execute(f"{go} env GOCACHE GOPATH GOTOOLCHAIN")
        npm_cache = backend.execute(f"{node} {npm_cli} cache verify")

        toolchain = scratch.resolve() / "toolchain"
        assert go_env.exit_code == 0, go_env.output
        assert go_env.output.split() == [
            str(toolchain / "GOCACHE"),
            str(toolchain / "GOPATH"),
            "local",
        ]
        assert npm_cache.exit_code == 0, npm_cache.output
        assert (
            f"({toolchain / 'npm_config_cache' / '_cacache'})" in npm_cache.output
        )
        after = sorted(str(p.relative_to(worktree)) for p in worktree.rglob("*"))
        assert after == before


# ---------------------------------------------------------------------------
# 13 October 2026 (proof defect 5): the read-only backend option.
# ---------------------------------------------------------------------------


def test_read_only_backend_refuses_writes_and_offers_no_execution(
    tmp_path: Path,
) -> None:
    import asyncio

    from deepagents.middleware.filesystem import supports_execution

    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / "app.py").write_text("ANSWER = 42\n")
    outside = Path("/tmp/count-check/build.mjs")
    outside_existed = outside.exists()

    backend = build_autobuild_backend(worktree, read_only=True)

    inside = backend.write(str(worktree / "scratch.mjs"), "console.log(1)\n")
    escaped = backend.write(str(outside), "console.log(1)\n")
    assert inside.error and "read-only" in inside.error
    assert escaped.error and "read-only" in escaped.error
    assert not (worktree / "scratch.mjs").exists()
    assert outside.exists() == outside_existed

    edited = backend.edit(str(worktree / "app.py"), "42", "43")
    deleted = backend.delete(str(worktree / "app.py"))
    async_write = asyncio.run(backend.awrite(str(worktree / "async.txt"), "x"))
    assert edited.error and deleted.error and async_write.error
    assert (worktree / "app.py").read_text() == "ANSWER = 42\n"
    assert not (worktree / "async.txt").exists()

    assert supports_execution(backend) is False
    assert not hasattr(backend.default, "execute")
    with pytest.raises(NotImplementedError):
        backend.execute("node --version")

    # Reading and searching still work.
    read = backend.read(str(worktree / "app.py"))
    assert "ANSWER = 42" in str(read.file_data or read)
    found = backend.grep("ANSWER", path=str(worktree))
    assert found.matches and found.matches[0]["path"].endswith("app.py")


def test_backend_without_read_only_is_unchanged(tmp_path: Path) -> None:
    from deepagents.middleware.filesystem import supports_execution

    backend = build_autobuild_backend(tmp_path)
    assert isinstance(backend.default, PathConfinedBackend)
    assert supports_execution(backend) is True
    assert backend.write(str(tmp_path / "kept.txt"), "x").error is None
    assert (tmp_path / "kept.txt").read_text() == "x"


def test_read_only_backend_refuses_uploads_and_writes_nothing(
    tmp_path: Path,
) -> None:
    import asyncio

    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / "app.py").write_text("ANSWER = 42\n")
    backend = build_autobuild_backend(worktree, read_only=True)
    # Snapshot after construction: the builder makes the private .tmp folder.
    before = sorted(p.relative_to(worktree) for p in worktree.rglob("*"))
    target = worktree / "uploaded.bin"
    outside = tmp_path / "outside.bin"

    for responses in (
        backend.upload_files([(str(target), b"x"), (str(outside), b"y")]),
        backend.default.upload_files([(str(target), b"x")]),
        asyncio.run(backend.aupload_files([(str(target), b"x")])),
        asyncio.run(backend.default.aupload_files([(str(outside), b"y")])),
    ):
        assert responses
        for response in responses:
            assert response.error and "read-only" in str(response.error)
    assert not target.exists() and not outside.exists()
    assert sorted(p.relative_to(worktree) for p in worktree.rglob("*")) == before

    # Reading, listing and downloading still pass through.
    (downloaded,) = backend.download_files([str(worktree / "app.py")])
    assert downloaded.error is None and downloaded.content == b"ANSWER = 42\n"
    listed = backend.ls(str(worktree))
    assert any(
        str(entry["path"]).endswith("app.py") for entry in (listed.entries or [])
    )


def test_summarisation_offload_with_read_only_backend_warns_and_carries_on(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    import base64
    import logging

    from deepagents.middleware.summarization import create_summarization_middleware
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage, HumanMessage

    worktree = tmp_path / "worktree"
    worktree.mkdir()
    backend = build_autobuild_backend(worktree, read_only=True)
    before = sorted(p.relative_to(worktree) for p in worktree.rglob("*"))
    middleware = create_summarization_middleware(
        GenericFakeChatModel(messages=iter([AIMessage(content="summary")])), backend
    )
    image = base64.b64encode(b"\x89PNG\r\n\x1a\nnot-really-a-png").decode()
    messages = [
        HumanMessage(
            content=[
                {"type": "text", "text": "look at this"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image}"}},
            ]
        ),
        AIMessage(content="seen"),
    ]

    with caplog.at_level(logging.WARNING):
        rewritten, failed = middleware._offload_inline_media(backend, messages)
        saved = middleware._offload_to_backend(backend, rewritten, "session-1")

    assert failed == 1
    assert saved is None
    warnings_text = "\n".join(r.getMessage() for r in caplog.records)
    assert "Failed to upload media" in warnings_text
    assert "Failed to offload conversation history" in warnings_text
    assert sorted(p.relative_to(worktree) for p in worktree.rglob("*")) == before
