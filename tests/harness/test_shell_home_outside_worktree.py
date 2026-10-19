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
  scratch folder, outside the project, and apart from the folder GuardKit's
  own project commands use, so nothing the builder leaves there changes the
  checks the build is judged by;
* a tool writing its caches under ``$HOME`` (npm, pip, Cargo, Go and so on)
  leaves nothing in the worktree, and GuardKit's git detection finds nothing;
* a project's ``launch.scratch`` declaration still works and wins for the
  names it lists;
* ``TMPDIR`` (which was ``<worktree>/.tmp``) is likewise a private folder
  of the shells' own, and a temporary file leaves nothing in the worktree.

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
    expected = (_scratch(worktree) / "toolchain" / "SHELL-HOME").resolve()

    for backend in (_builder_shell(worktree), _checker_shell(worktree)):
        result = backend.execute('printf "%s" "$HOME"')
        assert result.exit_code == 0, result.output
        home = Path(result.output.strip())
        assert home == expected
        assert home.is_dir()
        assert (home.stat().st_mode & 0o777) == 0o700
        assert not home.is_relative_to(worktree.resolve())


def test_the_shell_does_not_share_home_or_tmpdir_with_project_commands(
    tmp_path: Path,
) -> None:
    """The checks GuardKit runs never see what the builder's shell left.

    The coach's finding (19 October 2026): with one shared HOME, a ``.pth``
    file the builder put under ``~/.local`` was loaded by the project
    commands the build is judged by, while ``git status`` stayed empty.
    """
    from guardkit.orchestrator.project_command_env import (
        project_command_environment,
    )

    worktree = _factory_worktree(tmp_path)
    builder = _builder_shell(worktree)
    commands = project_command_environment(worktree, None)
    assert builder.default._env["HOME"] != commands["HOME"]
    assert builder.default._env["TMPDIR"] != commands["TMPDIR"]

    planted = builder.execute(
        'set -e; echo builder > "$HOME/left-by-builder"; '
        'echo builder > "$TMPDIR/left-by-builder"; '
        'echo "[user]" > "$HOME/.gitconfig"; echo "x=y" > "$HOME/.npmrc"'
    )
    assert planted.exit_code == 0, planted.output

    seen = subprocess.run(
        ["sh", "-c", 'ls -A "$HOME"; echo ---; ls -A "$TMPDIR"'],
        cwd=worktree, env=commands, capture_output=True, text=True, check=True,
    ).stdout
    assert "left-by-builder" not in seen
    assert ".gitconfig" not in seen and ".npmrc" not in seen
    assert _git(worktree, "status", "--porcelain", "--untracked-files=all") == ""


@pytest.mark.skipif(
    not Path("/usr/bin/python3").exists(), reason="no /usr/bin/python3 here"
)
def test_a_pth_file_the_builder_plants_is_not_loaded_by_project_commands(
    tmp_path: Path,
) -> None:
    """The coach's own reproduction, with a control showing the file works."""
    from guardkit.orchestrator.project_command_env import (
        project_command_environment,
    )

    python = "/usr/bin/python3"
    worktree = _factory_worktree(tmp_path)
    builder = _builder_shell(worktree)
    planted = builder.execute(
        f'set -e; site=$({python} -c "import site; print(site.getusersitepackages())"); '
        'mkdir -p "$site"; '
        "echo 'import os; os.environ[\"PLANTED_BY_BUILDER\"] = \"1\"' "
        '> "$site/planted.pth"'
    )
    assert planted.exit_code == 0, planted.output
    probe = [python, "-c", "import os; print(os.environ.get('PLANTED_BY_BUILDER', 'absent'))"]

    commands = project_command_environment(worktree, None)
    seen = subprocess.run(
        probe, cwd=worktree, env=commands, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert seen == "absent"
    # Control: given the builder's HOME, the same command does load it.
    control = dict(commands, HOME=builder.default._env["HOME"])
    loaded = subprocess.run(
        probe, cwd=worktree, env=control, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert loaded == "1"


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
    assert env["HOME"] == str((scratch / "toolchain" / "SHELL-HOME").resolve())
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
    assert env["HOME"] == str((scratch / "toolchain" / "SHELL-HOME").resolve())


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
    os.symlink(elsewhere, toolchain / "SHELL-HOME")

    with pytest.raises(ValueError, match="symlink"):
        shell_home(worktree)
    with pytest.raises(ValueError, match="symlink"):
        build_autobuild_backend(worktree)


def test_builder_and_checker_shells_have_tmpdir_outside_the_worktree(
    tmp_path: Path,
) -> None:
    worktree = _factory_worktree(tmp_path)
    expected = (_scratch(worktree) / "toolchain" / "SHELL-TMPDIR").resolve()

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


def test_an_existing_open_shell_folder_is_made_owner_only(tmp_path: Path) -> None:
    """19 October 2026: a pre-made 0777 folder is tightened, not taken as is."""
    worktree = _factory_worktree(tmp_path)
    toolchain = _scratch(worktree) / "toolchain"
    toolchain.mkdir(mode=0o700)
    for name in ("SHELL-HOME", "SHELL-TMPDIR", "TOOL_CACHE"):
        (toolchain / name).mkdir()
        (toolchain / name).chmod(0o777)
    toolchain.chmod(0o777)

    backend = _builder_shell(worktree, {"settings": [], "scratch": ["TOOL_CACHE"]})

    assert Path(backend.default._env["HOME"]) == (toolchain / "SHELL-HOME").resolve()
    names = ("SHELL-HOME", "SHELL-TMPDIR", "TOOL_CACHE")
    for folder in (toolchain, *(toolchain / name for name in names)):
        assert (folder.stat().st_mode & 0o777) == 0o700, folder


def test_a_shell_folder_owned_by_another_user_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worktree = _factory_worktree(tmp_path)
    toolchain = _scratch(worktree) / "toolchain"
    (toolchain / "SHELL-HOME").mkdir(parents=True)
    real_uid = os.geteuid()
    monkeypatch.setattr(os, "geteuid", lambda: real_uid + 1)

    with pytest.raises(ValueError, match="another user"):
        shell_home(worktree)


# ---------------------------------------------------------------------------
# 19 October 2026: one HOME and TMPDIR per role, so the builder's shell
# cannot change what the checker's shell runs.


def _role_shell(worktree: Path, role: str, *, builder: bool = False):
    return build_autobuild_backend(
        worktree,
        scratch_root=_scratch(worktree) if builder else None,
        shell_role=role,
    )


def test_each_role_gets_its_own_home_and_tmpdir(tmp_path: Path) -> None:
    worktree = _factory_worktree(tmp_path)
    toolchain = (_scratch(worktree) / "toolchain").resolve()

    seen = {}
    for role in ("builder", "checker", "specialist"):
        env = _role_shell(worktree, role, builder=role == "builder").default._env
        assert env["HOME"] == str(toolchain / f"{role}-SHELL-HOME")
        assert env["TMPDIR"] == str(toolchain / f"{role}-SHELL-TMPDIR")
        for name in ("HOME", "TMPDIR"):
            folder = Path(env[name])
            assert folder.is_dir()
            assert (folder.stat().st_mode & 0o777) == 0o700
            assert not folder.is_relative_to(worktree.resolve())
        seen[role] = (env["HOME"], env["TMPDIR"])
    homes = {home for home, _ in seen.values()}
    tmpdirs = {tmpdir for _, tmpdir in seen.values()}
    assert len(homes) == len(tmpdirs) == 3
    assert not (worktree / ".tmp").exists()


def test_what_the_builder_leaves_is_not_seen_by_the_checker(tmp_path: Path) -> None:
    worktree = _factory_worktree(tmp_path)
    (worktree / "test_sample.py").write_text(
        "import unittest\n\n\n"
        "class Sample(unittest.TestCase):\n"
        "    def test_adds(self):\n"
        "        self.assertEqual(1 + 1, 2)\n",
        encoding="utf-8",
    )
    _git(worktree, "add", "test_sample.py")
    _git(worktree, "commit", "-q", "-m", "a test")
    builder = _role_shell(worktree, "builder", builder=True)
    checker = _role_shell(worktree, "checker")

    planted = builder.execute(
        'set -e; echo builder > "$HOME/left-by-builder"; '
        'echo builder > "$TMPDIR/left-by-builder"; '
        'printf "[user]\\n\\tname = planted-by-builder\\n" > "$HOME/.gitconfig"; '
        'echo "registry=https://example.invalid/" > "$HOME/.npmrc"; '
        "git config --get user.name"
    )
    assert planted.exit_code == 0, planted.output
    # Control: the builder's own shell does read what it planted.
    assert "planted-by-builder" in planted.output

    looked = checker.execute(
        'ls -A "$HOME"; echo ---; ls -A "$TMPDIR"; echo ---; '
        'git config --get user.name || echo no-user-name'
    )
    assert looked.exit_code == 0, looked.output
    assert "left-by-builder" not in looked.output
    assert ".gitconfig" not in looked.output and ".npmrc" not in looked.output
    assert "planted-by-builder" not in looked.output
    assert "no-user-name" in looked.output

    # And the checker's shell still runs the project's tests normally.
    tests = checker.execute("python3 -m unittest -v test_sample")
    assert tests.exit_code == 0, tests.output
    assert "OK" in tests.output and "test_adds" in tests.output
    assert _detected_changes(worktree) == {"modified": [], "created": []}


def test_an_unknown_shell_role_is_refused_before_anything_is_made(
    tmp_path: Path,
) -> None:
    worktree = _factory_worktree(tmp_path)
    toolchain = _scratch(worktree) / "toolchain"

    with pytest.raises(ValueError, match="shell role"):
        build_autobuild_backend(worktree, shell_role="reviewer")
    assert not toolchain.exists()
    assert sorted(p.name for p in worktree.iterdir()) == [".git", "README.md"]
