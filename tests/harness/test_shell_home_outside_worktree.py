"""The shell's HOME and TMPDIR are never inside the build's worktree.

19 October 2026.

Build FEAT-B874 (ts-api-test): the builder ran ``npm install`` in its shell,
whose ``HOME`` was the worktree, and npm wrote 2,058 files of
``.npm/_cacache`` into the project. GuardKit's git detection then counted them
as the builder's new files. react-go-notes escaped only because it declares
``launch.scratch: [npm_config_cache, ...]``.

These tests build the shell the way GuardKit builds it, for a real linked git
worktree laid out like the factory's (``<host>/.guardkit/worktrees/FEAT-X``),
for a project with no ``launch:`` block, and show:

* the builder's and the checker's shells get ``HOME`` in GuardKit's builder
  scratch folder, the same folder GuardKit's own project commands use, outside
  the project;
* a tool writing its caches under ``$HOME`` (npm, pip, Cargo, Go and so on)
  leaves nothing in the worktree, and GuardKit's git detection finds nothing;
* a project's ``launch.scratch`` declaration still works and wins for the
  names it lists;
* ``TMPDIR`` (which was ``<worktree>/.tmp``) is likewise the project
  commands' private folder, and a temporary file leaves nothing in the
  worktree.

No tool or language is named in the code under test: every cache here follows
``HOME`` by the tool's own default.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from guardkitfactory import build_autobuild_backend
from guardkitfactory.harness import backend_config
from guardkitfactory.harness.backend_config import shell_home, shell_tmpdir

_GIT_ENV = {
    "PATH": "/usr/bin:/bin",
    "HOME": "/nonexistent",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
}

# What a package manager's install leaves under its default home-folder
# caches. Each line follows HOME the way the tool itself does by default.
_SIMULATED_INSTALL = (
    'set -e; '
    'mkdir -p "$HOME/.npm/_cacache/content-v2/sha512/ab" "$HOME/.npm/_logs"; '
    'echo blob > "$HOME/.npm/_cacache/content-v2/sha512/ab/cd"; '
    'echo log > "$HOME/.npm/_logs/debug-0.log"; '
    'mkdir -p "$HOME/.cache/pip/http"; echo x > "$HOME/.cache/pip/http/y"; '
    'mkdir -p "$HOME/.cargo/registry/cache"; echo x > "$HOME/.cargo/registry/cache/z"; '
    'mkdir -p "$HOME/go/pkg/mod/cache"; echo x > "$HOME/go/pkg/mod/cache/w"; '
    'echo "registry=https://example.invalid/" > ~/.npmrc; '
    'echo done'
)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, env=_GIT_ENV, check=True, capture_output=True,
        text=True,
    ).stdout


def _factory_worktree(tmp_path: Path, config: str | None = None) -> Path:
    """A host repository with one commit and a linked build worktree."""
    host = tmp_path / "host"
    host.mkdir()
    _git(host, "init", "-q")
    (host / "README.md").write_text("project\n", encoding="utf-8")
    if config is not None:
        (host / ".guardkit").mkdir()
        (host / ".guardkit" / "config.yaml").write_text(config, encoding="utf-8")
    _git(host, "add", "-A")
    _git(host, "commit", "-q", "-m", "start")
    worktree = host / ".guardkit" / "worktrees" / "FEAT-X"
    _git(host, "worktree", "add", "-q", "-b", "autobuild/FEAT-X", str(worktree))
    return worktree


def _scratch(worktree: Path) -> Path:
    from guardkit.orchestrator.paths import prepare_builder_scratch_dir

    scratch = prepare_builder_scratch_dir(worktree)
    assert scratch is not None
    return scratch


def _builder_shell(worktree: Path, launch: dict | None = None):
    """The builder's shell, through GuardKit's own call (the Player's route)."""
    from guardkit.orchestrator.harness.selector import (
        _build_backend_with_optional_cap,
    )

    return _build_backend_with_optional_cap(
        build_autobuild_backend, worktree, None, (), _scratch(worktree), launch, None
    )


def _checker_shell(worktree: Path):
    """The checker's (and specialists') shell: no scratch folder of its own."""
    from guardkit.orchestrator.harness.selector import (
        _build_backend_with_optional_cap,
    )

    return _build_backend_with_optional_cap(
        build_autobuild_backend, worktree, None, (), None, None, None
    )


def _detected_changes(worktree: Path) -> dict:
    """GuardKit's own post-turn git detection for this worktree."""
    from guardkit.orchestrator.agent_invoker import AgentInvoker

    invoker = AgentInvoker.__new__(AgentInvoker)
    invoker._git_lock = threading.Lock()
    invoker.worktree_path = worktree
    invoker._baseline_commit = None
    return invoker._detect_git_changes()


def test_builder_and_checker_shells_have_home_outside_the_worktree(
    tmp_path: Path,
) -> None:
    worktree = _factory_worktree(tmp_path)
    expected = (_scratch(worktree) / "toolchain" / "HOME").resolve()

    for backend in (_builder_shell(worktree), _checker_shell(worktree)):
        result = backend.execute('printf "%s" "$HOME"')
        assert result.exit_code == 0, result.output
        home = Path(result.output.strip())
        assert home == expected
        assert home.is_dir()
        assert (home.stat().st_mode & 0o777) == 0o700
        assert not home.is_relative_to(worktree.resolve())


def test_the_shell_shares_home_with_guardkits_project_commands(
    tmp_path: Path,
) -> None:
    from guardkit.orchestrator.project_command_env import (
        project_command_environment,
    )

    worktree = _factory_worktree(tmp_path)
    backend = _builder_shell(worktree)

    commands = project_command_environment(worktree, None)
    assert backend.default._env["HOME"] == commands["HOME"]
    assert backend.default._env["TMPDIR"] == commands["TMPDIR"]


def test_a_simulated_install_leaves_nothing_in_the_worktree(tmp_path: Path) -> None:
    worktree = _factory_worktree(tmp_path)
    before = _git(worktree, "status", "--porcelain", "--untracked-files=all", "--ignored")

    for backend in (_builder_shell(worktree), _checker_shell(worktree)):
        result = backend.execute(_SIMULATED_INSTALL)
        assert result.exit_code == 0, result.output

    home = Path(_builder_shell(worktree).default._env["HOME"])
    assert (home / ".npm" / "_cacache" / "content-v2" / "sha512" / "ab" / "cd").is_file()
    for name in (".npm", ".cache", ".cargo", "go", ".npmrc"):
        assert not (worktree / name).exists(), name
    after = _git(worktree, "status", "--porcelain", "--untracked-files=all", "--ignored")
    assert after == before == ""
    # GuardKit's git detection, the step that counted 2,058 cache files in
    # FEAT-B874, finds nothing.
    assert _detected_changes(worktree) == {"modified": [], "created": []}


def test_real_files_the_builder_writes_are_still_detected(tmp_path: Path) -> None:
    """The control: detection still works, it just has no caches to count."""
    worktree = _factory_worktree(tmp_path)
    backend = _builder_shell(worktree)

    result = backend.execute(_SIMULATED_INSTALL + "; echo code > src.txt")
    assert result.exit_code == 0, result.output

    assert _detected_changes(worktree) == {"modified": [], "created": ["src.txt"]}


@pytest.mark.skipif(shutil.which("npm") is None, reason="npm is not installed here")
def test_real_npm_resolves_its_cache_under_the_private_home(tmp_path: Path) -> None:
    """npm itself, asked offline where its cache is, answers the private HOME."""
    worktree = _factory_worktree(tmp_path)
    backend = _builder_shell(worktree)
    tool_dir = Path(shutil.which("npm")).parent

    result = backend.execute(
        f'PATH="{tool_dir}:$PATH" npm config get cache --offline'
    )

    assert result.exit_code == 0, result.output
    cache = Path(result.output.strip().splitlines()[-1])
    assert cache == Path(backend.default._env["HOME"]) / ".npm"
    assert not cache.is_relative_to(worktree.resolve())


def test_a_launch_scratch_declaration_still_works_and_wins(tmp_path: Path) -> None:
    worktree = _factory_worktree(tmp_path)
    scratch = _scratch(worktree)
    backend = _builder_shell(worktree, {"settings": [], "scratch": ["TOOL_CACHE"]})

    env = backend.default._env
    assert env["TOOL_CACHE"] == str((scratch / "toolchain" / "TOOL_CACHE").resolve())
    assert env["HOME"] == str((scratch / "toolchain" / "HOME").resolve())
    # A tool that honours its declared setting over its HOME default writes
    # where the project said.
    result = backend.execute(
        'cache="${TOOL_CACHE:-$HOME/.tool}"; '
        'mkdir -p "$cache/blobs" && echo x > "$cache/blobs/a"'
    )
    assert result.exit_code == 0, result.output
    assert (scratch / "toolchain" / "TOOL_CACHE" / "blobs" / "a").is_file()
    assert not (Path(env["HOME"]) / ".tool").exists()
    assert _detected_changes(worktree) == {"modified": [], "created": []}


def test_a_launch_scratch_declaration_read_from_the_project_still_applies(
    tmp_path: Path,
) -> None:
    """The whole route: GuardKit reads the project's block, the shell applies it."""
    from guardkit.orchestrator.launch_declaration import (
        load_launch_declaration,
        main_checkout_root,
    )

    worktree = _factory_worktree(
        tmp_path, "launch:\n  scratch: [npm_config_cache]\n"
    )
    declaration = load_launch_declaration(main_checkout_root(worktree))
    assert declaration is not None and not declaration.is_empty
    backend = _builder_shell(worktree, declaration.as_backend_argument())

    env = backend.default._env
    scratch = _scratch(worktree)
    assert env["npm_config_cache"] == str(
        (scratch / "toolchain" / "npm_config_cache").resolve()
    )
    assert env["HOME"] == str((scratch / "toolchain" / "HOME").resolve())


def test_a_worktree_without_git_gets_a_private_temporary_home(tmp_path: Path) -> None:
    worktree = tmp_path / "plain"
    worktree.mkdir()

    first = Path(build_autobuild_backend(worktree).default._env["HOME"])
    second = Path(build_autobuild_backend(worktree).default._env["HOME"])

    assert first == second
    assert first.is_dir()
    assert not first.is_relative_to(worktree.resolve())
    backend_config._remove_temporary_model_artifacts()
    assert not first.exists()


def test_a_symlinked_home_folder_is_refused(tmp_path: Path) -> None:
    worktree = _factory_worktree(tmp_path)
    toolchain = _scratch(worktree) / "toolchain"
    toolchain.mkdir(mode=0o700)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    os.symlink(elsewhere, toolchain / "HOME")

    with pytest.raises(ValueError, match="symlink"):
        shell_home(worktree)
    with pytest.raises(ValueError, match="symlink"):
        build_autobuild_backend(worktree)


def test_builder_and_checker_shells_have_tmpdir_outside_the_worktree(
    tmp_path: Path,
) -> None:
    worktree = _factory_worktree(tmp_path)
    expected = (_scratch(worktree) / "toolchain" / "TMPDIR").resolve()

    for backend in (_builder_shell(worktree), _checker_shell(worktree)):
        result = backend.execute('printf "%s" "$TMPDIR"')
        assert result.exit_code == 0, result.output
        tmpdir = Path(result.output.strip())
        assert tmpdir == expected == shell_tmpdir(worktree)
        assert tmpdir.is_dir()
        assert (tmpdir.stat().st_mode & 0o777) == 0o700
        assert not tmpdir.is_relative_to(worktree.resolve())
    assert not (worktree / ".tmp").exists()


def test_a_write_to_tmpdir_leaves_nothing_in_the_worktree(tmp_path: Path) -> None:
    worktree = _factory_worktree(tmp_path)

    for backend in (_builder_shell(worktree), _checker_shell(worktree)):
        result = backend.execute(
            'set -e; mkdir -p "$TMPDIR/node-compile-cache/v22"; '
            'echo x > "$TMPDIR/node-compile-cache/v22/entry"; '
            'made=$(mktemp); echo y > "$made"; '
            'made_dir=$(mktemp -d); echo z > "$made_dir/f"; echo "$made"'
        )
        assert result.exit_code == 0, result.output
        made = Path(result.output.strip().splitlines()[-1])
        assert made.parent == shell_tmpdir(worktree)

    tmpdir = shell_tmpdir(worktree)
    assert (tmpdir / "node-compile-cache" / "v22" / "entry").is_file()
    assert not (worktree / ".tmp").exists()
    status = _git(worktree, "status", "--porcelain", "--untracked-files=all", "--ignored")
    assert status == ""
    assert _detected_changes(worktree) == {"modified": [], "created": []}


def test_a_worktree_without_git_gets_a_private_temporary_tmpdir(
    tmp_path: Path,
) -> None:
    worktree = tmp_path / "plain"
    worktree.mkdir()

    first = build_autobuild_backend(worktree).default._env
    second = build_autobuild_backend(worktree).default._env

    tmpdir = Path(first["TMPDIR"])
    assert tmpdir == Path(second["TMPDIR"])
    assert tmpdir.is_dir()
    assert tmpdir != Path(first["HOME"])
    assert not tmpdir.is_relative_to(worktree.resolve())
    assert list(worktree.iterdir()) == []
    backend_config._remove_temporary_model_artifacts()
    assert not tmpdir.exists()
