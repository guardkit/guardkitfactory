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

import time
from pathlib import Path
from typing import Literal

import pytest
import wcmatch.glob as wcglob
from deepagents import FilesystemPermission
from deepagents.backends.composite import CompositeBackend
from deepagents.backends.local_shell import LocalShellBackend

from guardkitfactory import build_autobuild_backend, build_autobuild_permissions

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
    summarisation middleware reads to compute its offload prefix. Empty
    routes means the wrapper is a transparent pass-through for every other
    operation — the underlying ``LocalShellBackend`` still owns the on-disk
    behaviour. See ``backend_config.py`` module docstring for the chain.
    """
    backend = build_autobuild_backend(tmp_path)
    assert isinstance(backend, CompositeBackend)
    assert isinstance(backend.default, LocalShellBackend)
    assert backend.routes == {}


def test_build_autobuild_backend_artifacts_root_is_worktree(
    tmp_path: Path,
) -> None:
    """TASK-HMIG-002R-SUMM-ROOT: artifacts_root points at the worktree.

    Without this, deepagents' summarisation middleware falls back to ``"/"``
    and computes ``/conversation_history`` as the offload prefix — which
    under NOVMODE's ``virtual_mode=False`` resolves to host root (read-only)
    and crashes the offload, leaving conversation history un-summarised
    until the model context overflows. See ``autobuild-FEAT-AOF-run-2.md``
    lines 342-350.
    """
    backend = build_autobuild_backend(tmp_path)
    assert backend.artifacts_root == str(tmp_path.resolve())


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
    assert backend.default._env["HOME"] == str(tmp_path)
    assert backend.default._env["TMPDIR"] == str(tmp_path / ".tmp")


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


def test_summarization_offload_path_lands_inside_worktree(tmp_path: Path) -> None:
    """The conversation-history offload write must succeed under the worktree.

    Reproduces the path the SDK summarisation middleware would compute:
    ``f"{artifacts_root.rstrip('/')}/conversation_history/<thread>.md"``.
    Under the SUMM-ROOT wrapper, that resolves to a worktree-rooted file
    the orchestrator process can write. Before the fix, ``artifacts_root``
    defaulted to ``"/"`` and the write target was ``/conversation_history/...``
    (host root) — write-fails on every standard macOS / Linux deployment.
    """
    backend = build_autobuild_backend(tmp_path)

    # Compute the path exactly the way deepagents does (summarization.py
    # line 296). Resolving artifacts_root with rstrip mirrors the SDK.
    prefix = f"{backend.artifacts_root.rstrip('/')}/conversation_history"
    offload_target = f"{prefix}/session_abc.md"

    result = backend.write(offload_target, "# offloaded turn 1\n")
    assert result.error is None, (
        f"offload write rejected — SUMM-ROOT regression? error={result.error!r} "
        f"target={offload_target!r}"
    )

    expected = tmp_path.resolve() / "conversation_history" / "session_abc.md"
    assert expected.is_file(), (
        f"offload file did not materialise inside the worktree (expected {expected})"
    )


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
    assert prefix.startswith(str(tmp_path.resolve())), (
        f"offload prefix {prefix!r} is not under the worktree {tmp_path.resolve()!r}"
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


def test_build_autobuild_permissions_is_empty_until_upstream_lands_or_custom_middleware_ships() -> None:
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
