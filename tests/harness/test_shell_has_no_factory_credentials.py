"""The model shells and the BDD plugins hold no factory credentials.

13 October 2026. Design: ``docs/designs/factory-project-commands-without-
factory-credentials-2026-10-13.md``, section 1b and the
guardkitfactory tests.

* The builder's and the checker's shells (``build_autobuild_backend``) keep
  their own base (``PATH``, ``HOME`` at the worktree, ``TMPDIR``, the Python
  flags, the declared settings and scratch folders) and then pass it through
  GuardKit's ``finish_project_environment``: a declared proxy that carries a
  user name or password refuses construction, and the run-owner marker reaches
  the shell from this process alone.
* The BDD plugins (G1 to G4) build their commands' environment with GuardKit's
  ``project_command_environment``.
* ``test_every_process_launch_is_accounted_for`` fails on any process launch in
  the package that neither uses the helper nor is one of the factory's own
  programs.
"""

from __future__ import annotations

import ast
import logging
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import pytest

from guardkitfactory.harness import build_autobuild_backend

SENTINEL_NAMES = (
    "GUARDKIT_NATS_PASSWORD",
    "FLEET_MEMORY_PG_DSN",
    "FLEET_MEMORY_NATS_URL",
    "FORGE_NATS_URL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "ANTHROPIC_API_KEY",
    "FORGE_DB_PATH",
    "SSH_AUTH_SOCK",
)
MARK = "SENTINEL-c4f1"
_PROXIES = [
    name
    for base in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY", "FTP_PROXY")
    for name in (base, base.lower())
]


def _parse_env(text: str) -> Dict[str, str]:
    env: Dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            name, value = line.split("=", 1)
            env[name] = value
    return env


def _assert_no_sentinel(env: Dict[str, str], where: str) -> None:
    leaked = sorted(n for n, v in env.items() if MARK in v or n in SENTINEL_NAMES)
    assert not leaked, f"{where}: the factory's settings reached the project: {leaked}"


@pytest.fixture()
def factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    for name in SENTINEL_NAMES:
        monkeypatch.setenv(name, f"{MARK}-{name}")
    for name in _PROXIES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("STANDIN_SETTING", "present")
    monkeypatch.setenv("GUARDKIT_RUN_OWNER", "build-x")
    host = tmp_path / "host"
    worktree = host / ".guardkit" / "worktrees" / "FEAT-X"
    worktree.mkdir(parents=True)
    git_dir = host / ".git" / "worktrees" / "FEAT-X"
    git_dir.mkdir(parents=True)
    (worktree / ".git").write_text(f"gitdir: {git_dir}\n", encoding="utf-8")
    (host / ".guardkit" / "config.yaml").write_text(
        "launch:\n  settings: [STANDIN_SETTING]\n  scratch: [STANDIN_CACHE]\n",
        encoding="utf-8",
    )
    return SimpleNamespace(
        worktree=worktree, scratch=git_dir / "guardkit-scratch", out=tmp_path / "seen"
    )


_LAUNCH = {"settings": ["STANDIN_SETTING"], "scratch": ["STANDIN_CACHE"]}


@pytest.mark.parametrize("role", ["builder", "checker"])
def test_the_shell_has_no_factory_credentials(factory, role: str) -> None:
    if role == "builder":
        backend = build_autobuild_backend(
            factory.worktree, scratch_root=factory.scratch, launch_environment=_LAUNCH
        )
    else:
        backend = build_autobuild_backend(
            factory.worktree, launch_scratch_root=factory.scratch, launch_environment=_LAUNCH
        )
    result = backend.execute("env")
    assert result.exit_code == 0, result.output
    seen = _parse_env(result.output)
    _assert_no_sentinel(seen, f"the {role}'s shell")
    assert seen.get("STANDIN_SETTING") == "present"
    assert Path(seen["STANDIN_CACHE"]).name == "STANDIN_CACHE"
    assert Path(seen["STANDIN_CACHE"]).is_dir()
    assert seen.get("GUARDKIT_RUN_OWNER") == "build-x"
    # The builder's shell keeps HOME at the worktree (coordinator decision 3).
    assert seen["HOME"] == str(factory.worktree)


@pytest.mark.parametrize("name", ["HTTPS_PROXY", "https_proxy"])
def test_a_declared_proxy_with_credentials_refuses_the_shell(
    factory, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, name: str
) -> None:
    monkeypatch.setenv(name, f"http://u:{MARK}@p:3128")
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(OSError) as caught:
            build_autobuild_backend(
                factory.worktree, scratch_root=factory.scratch,
                launch_environment={"settings": [name]},
            )
    assert name in str(caught.value)
    assert MARK not in str(caught.value)
    assert MARK not in caplog.text

    # A declared proxy without credentials still arrives.
    monkeypatch.setenv(name, "http://p:3128")
    backend = build_autobuild_backend(
        factory.worktree, scratch_root=factory.scratch,
        launch_environment={"settings": [name]},
    )
    assert _parse_env(backend.execute("env").output).get(name) == "http://p:3128"


def _plant(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def test_the_bdd_plugins_hide_factory_credentials(factory) -> None:
    from guardkitfactory.bdd.plugin import StackProfile
    from guardkitfactory.bdd.plugins.cucumber_js_plugin import CucumberJSPlugin
    from guardkitfactory.bdd.plugins.pytest_bdd_plugin import PytestBDDPlugin
    from guardkitfactory.bdd.plugins.reqnroll_plugin import ReqnrollPlugin

    out = factory.out
    out.mkdir()
    wt = factory.worktree
    dump = f'env > "{out}/$LABEL.env"\n'

    # G1: a planted pytest_bdd.py in the work folder stands in for the module.
    _plant(wt / "pytest_bdd.py",
           f"import os\nopen({str(out / 'g1.env')!r}, 'w').write("
           "'\\n'.join(k + '=' + v for k, v in os.environ.items()))\n")
    PytestBDDPlugin.discover(
        StackProfile("python", "pytest", "pip", wt, {"venv_python": sys.executable}), wt
    )
    (wt / "pytest_bdd.py").unlink()  # it would shadow the real plugin for G2
    # G2: the run of the project's scenarios.
    _plant(wt / "features" / "conftest.py",
           f"import os\nopen({str(out / 'g2.env')!r}, 'w').write("
           "'\\n'.join(k + '=' + v for k, v in os.environ.items()))\n")
    g2_result = PytestBDDPlugin().run([], "TASK-G2", wt, timeout_seconds=60)
    # G3: npx finds a planted node_modules/.bin/cucumber-js.
    (wt / "package.json").write_text('{"devDependencies": {"@cucumber/cucumber": "1"}}')
    _plant(wt / "node_modules" / ".bin" / "cucumber-js", "#!/bin/sh\nLABEL=g3\n" + dump)
    # G4: dotnet, as the project's PATH resolves it (a stand-in here).
    tools = out.parent / "tools"
    _plant(tools / "dotnet", "#!/bin/sh\nLABEL=g4\n" + dump)
    (wt / "x.csproj").write_text("<Project/>")
    os.environ["PATH"] = f"{tools}{os.pathsep}{os.environ['PATH']}"
    try:
        CucumberJSPlugin.discover(StackProfile("javascript", "cucumber", "npm", wt), wt)
        ReqnrollPlugin.discover(StackProfile("dotnet", "xunit", "dotnet", wt), wt)
    finally:
        os.environ["PATH"] = os.environ["PATH"].split(os.pathsep, 1)[1]

    labels = ["g1", "g2", "g4"]
    if (out / "g3.env").exists() or _which("npx"):
        labels.append("g3")
    for label in labels:
        path = out / f"{label}.env"
        assert path.exists(), f"{label} never ran: {g2_result}"
        _assert_no_sentinel(_parse_env(path.read_text()), label)
    g2 = _parse_env((out / "g2.env").read_text())
    assert g2.get("GUARDKIT_BDD_TASK_ID") == "TASK-G2"
    assert g2.get("STANDIN_SETTING") == "present"


def test_a_credentialed_proxy_in_this_process_does_not_break_the_import(factory) -> None:
    """The pytest-bdd plugin's contract checks run at import; they must not
    depend on this process's own settings, and a real run is still refused
    by name (13 October 2026, coach review fix 1)."""
    script = textwrap.dedent(
        f"""\
        import guardkitfactory
        from guardkitfactory.bdd.loader import _REGISTRY
        from guardkitfactory.bdd.plugins.pytest_bdd_plugin import PytestBDDPlugin
        assert PytestBDDPlugin in _REGISTRY, _REGISTRY
        result = PytestBDDPlugin().run([], "TASK-P1", __import__("pathlib").Path({str(factory.worktree)!r}))
        print(result.errors)
        """
    )
    env = dict(os.environ)
    env["HTTPS_PROXY"] = f"http://user:{MARK}@proxy:3128"
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    run = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, env=env, timeout=300
    )
    assert run.returncode == 0, run.stderr[-3000:]
    assert "could not start" in run.stdout and "HTTPS_PROXY" in run.stdout
    assert MARK not in run.stdout + run.stderr


def test_a_failing_built_in_plugin_does_not_take_down_the_import(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from guardkitfactory.bdd import plugins
    from guardkitfactory.bdd.loader import ContractTestFailure

    def _fail() -> Any:
        raise ContractTestFailure("PytestBDDPlugin failed its checks")

    with caplog.at_level(logging.ERROR):
        assert plugins._load("PytestBDDPlugin", _fail) is None
    assert "is not registered" in caplog.text
    # The real loaders still give the registered classes.
    assert plugins._pytest_bdd() is plugins.PytestBDDPlugin is not None


@pytest.mark.skipif(not Path("/proc/self/stat").exists(), reason="needs /proc")
def test_a_timed_out_bdd_run_leaves_nothing_running(
    factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pytest-bdd run uses GuardKit's process-group runner: a timeout
    ends everything the run started (13 October 2026)."""
    import time

    from guardkitfactory.bdd.plugins.pytest_bdd_plugin import PytestBDDPlugin

    factory.out.mkdir()
    pid = factory.out / "bdd.pid"
    script = factory.out / "python.sh"
    script.write_text(f'#!/bin/sh\nsleep 300 &\necho $! > "{pid}"\nwait\n', encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("GUARDKIT_BDD_VENV_PYTHON", str(script))
    result = PytestBDDPlugin().run([], "TASK-T1", factory.worktree, timeout_seconds=1)
    assert result.errors == ["timeout"]
    child = int(pid.read_text().strip())

    def running() -> bool:
        try:
            with open(f"/proc/{child}/stat", encoding="utf-8") as fh:
                return fh.read().rsplit(")", 1)[1].split()[0] != "Z"
        except OSError:
            return False

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and running():
        time.sleep(0.1)
    assert not running(), f"the run's child {child} is still running"


def _which(name: str) -> Optional[str]:
    import shutil

    return shutil.which(name)


# ---------------------------------------------------------------------------
# Section 5: every process launch in the package is accounted for
# ---------------------------------------------------------------------------

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "guardkitfactory"

#: Launches that are allowed as they are, with a one-line reason each.
ALLOWED: Dict[Tuple[str, str], str] = {
    ("bdd/plugin.py", "run_project_command"): (
        "passes its caller's arguments to GuardKit's run_project_command; "
        "every call to it is checked"
    ),
    ("code_search.py", "toolkit"): (
        "the factory's own pinned search programs' --version, with a fixed "
        "six-name environment (_git_environment)"
    ),
    ("code_search.py", "_execute"): (
        "the factory's own pinned search programs and git, with a fixed "
        "six-name environment (_git_environment)"
    ),
}

#: This package has no generic runners of its own. GuardKit's are listed so
#: a call to one from here is checked like a launch (they live in GuardKit,
#: hence the ``guardkit:`` prefix, which the allowed-list check skips).
GENERIC_RUNNERS: Dict[Tuple[str, str], Dict[str, Any]] = {
    ("guardkit:orchestrator/process_group.py", "run_in_own_group"): {
        "names": {"run_in_own_group"},
    },
    ("guardkit:orchestrator/process_group.py", "run_project_command"): {
        "names": {"run_project_command"},
    },
    ("bdd/plugin.py", "run_project_command"): {
        "names": {"run_project_command"},
    },
    ("guardkit:orchestrator/quality_gates/coach_validator.py", "_run_recorded"): {
        "names": {"_run_recorded"},
    },
    ("guardkit:orchestrator/completion_verification.py", "run_completion_verification"): {
        "names": {"run_completion_verification"},
        "default_is_safe": True,
    },
    ("guardkit:orchestrator/run_evidence.py", "start_command_evidence"): {
        "names": {"start_command_evidence", "CommandEvidence"},
        "none_is_safe": True,
    },
}

#: Places that use a module object other than as an attribute base, or
#: import code dynamically, and why each is safe (14 October 2026). Only
#: those rules are waived there (and only here: an ALLOWED entry does not
#: waive them); every launch rule still applies. Each entry must still be
#: needed (test_every_module_use_allowance_is_still_needed).
MODULE_USE_ALLOWED: Dict[Tuple[str, str], str] = {}

#: The repository's helper, by the dotted name it is imported from. A
#: launch whose ``env=`` is a call to it (or to a function that only ever
#: returns its result, found by module and function, never by bare name) is
#: a project command done right.
HELPERS = {
    "guardkit.orchestrator.project_command_env.project_command_environment",
    "guardkit.orchestrator.project_command_env.finish_project_environment",
}
#: ``finish_project_environment`` copies its input and adds to it; it is no
#: sanitiser. A call to it counts only when its input is itself the helper's.
_FINISH = "guardkit.orchestrator.project_command_env.finish_project_environment"

#: The factory's own programs, recognised from a literal first argument.
FACTORY_PROGRAMS = {"git", "docker", "pgrep", "ps"}

#: Every name a process launch goes by, in any launch module.
LAUNCH_NAMES = {
    "run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput",
    "create_subprocess_exec", "create_subprocess_shell", "subprocess_exec", "subprocess_shell",
    "system", "popen", "startfile",
    "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe",
    "spawn", "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe",
    "posix_spawn", "posix_spawnp", "fork", "forkpty",
}
#: Launch-shaped names that run no process: asyncio's event-loop runner.
NOT_LAUNCHES = {"asyncio.run", "asyncio.runners.run"}
#: The modules launches live in; their submodules count too (asyncio.subprocess).
LAUNCH_MODULES = {"subprocess", "os", "asyncio", "pty", "multiprocessing", "posix", "nt"}
#: Launch methods recognised on any object: an event loop's
#: ``subprocess_exec`` / ``subprocess_shell`` and ``create_subprocess_*``.
_ANY_RECEIVER_LAUNCHES = {
    "create_subprocess_exec", "create_subprocess_shell", "subprocess_exec", "subprocess_shell",
}


_REAL_SUBMODULES: Dict[str, bool] = {}


def _is_launch_module(dotted: str) -> bool:
    """A launch module, or a REAL submodule of one (asyncio.subprocess,
    os.path), never an attribute that only looks like one (os.getenv,
    asyncio.subprocess.create_subprocess_shell): below the top level the name
    must be importable as a module (``importlib.util.find_spec``)."""
    if dotted in LAUNCH_MODULES:
        return True
    if not any(dotted.startswith(m + ".") for m in LAUNCH_MODULES):
        return False
    if dotted not in _REAL_SUBMODULES:
        import importlib.util

        try:
            _REAL_SUBMODULES[dotted] = importlib.util.find_spec(dotted) is not None
        except (ImportError, AttributeError, ValueError):
            _REAL_SUBMODULES[dotted] = False
    return _REAL_SUBMODULES[dotted]


def _is_launch_target(dotted: str) -> bool:
    """THE ONE PREDICATE for a launch function: its resolved name ends in a
    launch name and its module is a launch module or a submodule of one. Used
    for direct, attribute and bare imported calls, guarded names and the
    alias rule alike, so no form can fall through a table gap."""
    module, _, last = dotted.rpartition(".")
    if dotted in NOT_LAUNCHES:
        return False
    return bool(module) and last in LAUNCH_NAMES and _is_launch_module(module)
class _Module(SimpleNamespace):
    rel: str
    dotted: str
    tree: ast.Module
    parents: Dict[int, ast.AST]
    imports: Dict[str, str]


def _load_modules(package: Path) -> List[_Module]:
    modules = []
    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents: Dict[int, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[id(child)] = node
        rel = str(path.relative_to(package))
        parts = [package.name, *Path(rel).with_suffix("").parts]
        is_package = parts[-1] == "__init__"
        if is_package:
            parts = parts[:-1]
        dotted = ".".join(parts)
        modules.append(
            _Module(
                rel=rel, dotted=dotted, tree=tree, parents=parents,
                imports=_imports(tree, dotted, is_package),
            )
        )
    # Shared by every module: the package's modules by dotted name, the
    # identities that end a chain whatever the scanned tree holds (the
    # helper and every generic runner), and the followed-name cache.
    index = {m.dotted: m for m in modules}
    known = set(HELPERS) | {
        _runner_identity(package.name, rel, fname) for rel, fname in GENERIC_RUNNERS
    }
    finals: Dict[str, frozenset] = {}
    for m in modules:
        m.index, m.known, m.finals = index, known, finals
        m.root = package.name
    return modules


#: Marks the point in a dotted name past which a re-export could not be
#: followed (``pkg.api.name<unfollowed>`` or ``pkg.api.name<unfollowed>.attr``).
_UNFOLLOWED = "<unfollowed>"


def _final_identities(mod: "_Module", dotted: str) -> set:
    """What ``dotted`` finally names, following re-exports inside the
    scanned package (14 October 2026).

    A name taken from a module of the package is looked up in that module:
    one plain import is followed (cycle-safe, any number of hops, the rest
    of an attribute chain carried along); one def or class, or one plain
    assignment, ends the chain there (storing a launch, runner or launch
    module in a name is itself a violation where it is stored); anything
    else (no binding in an existing module or no such module at all, a
    cycle, several bindings, a ``global``) cannot be followed and is marked
    :data:`_UNFOLLOWED`, after following whatever imports it does have.
    Names outside the package, the package's own modules and the known
    identities (the helper, the generic runners, and modules that hold them)
    are final as they are."""
    if dotted not in mod.finals:
        out: set = set()
        _follow(mod, dotted, frozenset(), out)
        mod.finals[dotted] = frozenset(out)
    return set(mod.finals[dotted])


def _follow(mod: "_Module", dotted: str, seen: frozenset, out: set) -> None:
    index, known = mod.index, mod.known
    if (
        _UNFOLLOWED in dotted
        or dotted in known
        or any(k.startswith(dotted + ".") for k in known)
    ):
        out.add(dotted)
        return
    parts = dotted.split(".")
    for i in range(len(parts), 0, -1):
        if ".".join(parts[:i]) in index:
            break
    else:
        out.add(dotted)  # outside the scanned package
        return
    if i == len(parts):
        # Only the WHOLE name, never a shorter prefix: when the package's
        # __init__ also binds this name, ``from package import name`` gives
        # that binding. A package importing its own submodule under the same
        # name adds nothing. A package importing a name FROM that same
        # submodule (``from .resolve import resolve``, the allowed idiom)
        # replaces the module: the name is that binding only. Any other
        # binding (refused by _init_submodule_collisions anyway) keeps both.
        package = index.get(".".join(parts[:-1])) if len(parts) > 1 else None
        sites: List[Tuple[str, ast.AST, Optional[str]]] = []
        if package is not None and package.rel.endswith("__init__.py") and dotted not in seen:
            sites = [
                site
                for site in _binding_sites(
                    _module_scope_nodes(package), parts[-1], package.dotted, True
                )
                if not (site[0] == "import" and site[2] == dotted)
            ]
        if not sites or not all(
            site[0] == "import" and str(site[2]).startswith(dotted + ".") for site in sites
        ):
            out.add(dotted)  # a module of the package
        if sites:
            _follow_binding(mod, package, parts[-1], [], sites, seen | {dotted}, out)
        return
    if dotted in seen:
        out.add(".".join(parts[: i + 1]) + _UNFOLLOWED + "".join(f".{r}" for r in parts[i + 1:]))
        return  # a cycle
    exporter = index[".".join(parts[:i])]
    sites = _binding_sites(
        _module_scope_nodes(exporter), parts[i], exporter.dotted,
        exporter.rel.endswith("__init__.py"),
    )
    _follow_binding(mod, exporter, parts[i], parts[i + 1:], sites, seen | {dotted}, out)


def _follow_binding(
    mod: "_Module", exporter: "_Module", name: str, rest: List[str],
    sites: List[Tuple[str, ast.AST, Optional[str]]], seen: frozenset, out: set,
) -> None:
    """Follow how ``exporter`` binds ``name`` at module scope (``sites``),
    carrying the ``rest`` of an attribute chain (see :func:`_final_identities`)."""
    dotted = ".".join([exporter.dotted, name, *rest])
    unfollowed = f"{exporter.dotted}.{name}{_UNFOLLOWED}" + "".join(f".{r}" for r in rest)
    declared = any(
        isinstance(n, (ast.Global, ast.Nonlocal)) and name in n.names
        for n in ast.walk(exporter.tree)
    )
    imports = [target for kind, _node, target in sites if kind == "import"]
    if len(sites) == 1 and not declared:
        kind, node, target = sites[0]
        if kind == "def":
            out.add(dotted)  # its own definition
            return
        if kind == "import":
            _follow(mod, ".".join([target, *rest]), seen, out)
            return
        parent = exporter.parents.get(id(node))
        if kind == "name" and (
            (isinstance(parent, ast.Assign) and len(parent.targets) == 1 and parent.targets[0] is node)
            or (isinstance(parent, ast.AnnAssign) and parent.target is node and parent.value is not None)
        ):
            out.add(dotted)  # one plain assignment: the chain ends here
            return
    for target in sorted(set(imports)):
        _follow(mod, ".".join([target, *rest]), seen, out)
    if not sites:
        # No such module or no such name: whatever is reached through it,
        # attributes included, is unknown, so the whole name is.
        unfollowed = dotted + _UNFOLLOWED
    out.add(unfollowed)


def _final_targets(mod: "_Module", targets: Iterable[str]) -> set:
    """:func:`_final_identities` of every target in ``targets``."""
    out: set = set()
    for target in targets:
        out |= _final_identities(mod, target)
    return out


def _import_bindings(node: ast.AST, dotted: str, is_package: bool) -> List[Tuple[str, str]]:
    """The (bound name, what it names) pairs one import statement makes."""
    package = dotted if is_package else dotted.rsplit(".", 1)[0]
    out: List[Tuple[str, str]] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.asname:
                out.append((alias.asname, alias.name))
            else:
                out.append((alias.name.split(".")[0], alias.name.split(".")[0]))
    elif isinstance(node, ast.ImportFrom):
        base = node.module or ""
        if node.level:
            anchor = package.split(".")
            anchor = anchor[: len(anchor) - (node.level - 1)]
            base = ".".join([*anchor, base] if base else anchor)
        for alias in node.names:
            out.append((alias.asname or alias.name, f"{base}.{alias.name}"))
    return out


def _imports(tree: ast.Module, dotted: str, is_package: bool) -> Dict[str, set]:
    """Every name an import binds anywhere in the module, in any scope, ->
    the SET of everything it is imported as (never overwritten).

    A call through a name is a launch if ANY of its targets is a launch
    module or function (strict side); a helper or runner qualifies only when
    ALL of them are it (see :func:`_resolve`)."""
    out: Dict[str, set] = {}
    for node in ast.walk(tree):
        for name, target in _import_bindings(node, dotted, is_package):
            out.setdefault(name, set()).add(target)
    return out


def _names_bound_by(node: ast.AST, dotted: str, is_package: bool) -> List[Tuple[str, str, Optional[str]]]:
    """Every name ``node`` binds, as (name, kind, import target).

    THE ONE ENUMERATION of Python's binding forms, used by every "bound
    exactly once" and "not shadowed" decision in this guard: a name stored or
    deleted (plain, chained, unpacking, augmented, annotated and walrus
    assignment; for, with and comprehension targets; ``del``), a parameter
    (a lambda's included), an import or import-from alias, a def or class, an
    except target, a global or nonlocal declaration, and a match-case capture
    (``case x``, ``*rest``, ``**rest``). Kinds: name, param, import, def,
    except, declare, match."""
    if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
        return [(node.id, "name", None)]
    if isinstance(node, ast.arg):
        return [(node.arg, "param", None)]
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return [(bound, "import", target) for bound, target in _import_bindings(node, dotted, is_package)]
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [(node.name, "def", None)]
    if isinstance(node, ast.ExceptHandler) and node.name:
        return [(node.name, "except", None)]
    if isinstance(node, (ast.Global, ast.Nonlocal)):
        return [(name, "declare", None) for name in node.names]
    if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
        return [(node.name, "match", None)]
    if isinstance(node, ast.MatchMapping) and node.rest:
        return [(node.rest, "match", None)]
    return []


def _binding_sites(
    nodes: Iterable[ast.AST], name: str, dotted: str, is_package: bool, own: Optional[ast.AST] = None
) -> List[Tuple[str, ast.AST, Optional[str]]]:
    """Where ``name`` is bound among ``nodes`` (``own``, the function being
    looked into, does not bind its own name inside itself)."""
    sites: List[Tuple[str, ast.AST, Optional[str]]] = []
    for node in nodes:
        if node is own:
            continue
        for bound, kind, target in _names_bound_by(node, dotted, is_package):
            if bound == name:
                sites.append((kind, node, target))
    return sites


def _bindings(nodes: Iterable[ast.AST], name: str, dotted: str, is_package: bool, own: Optional[ast.AST] = None) -> Tuple[set, bool, bool]:
    """How ``name`` is bound among ``nodes``: (import targets, defined by a
    def or class, bound any other way), from :func:`_binding_sites`."""
    imports: set = set()
    definitions = 0
    other = False
    for kind, _node, target in _binding_sites(nodes, name, dotted, is_package, own):
        if kind == "import":
            imports.add(target)
        elif kind == "def":
            definitions += 1
        else:
            other = True
    # Defined more than once (under if/else, or twice): which one runs is
    # not known, so it is not a definition the guard can rely on.
    if definitions > 1:
        other = True
    return imports, definitions == 1, other


def _module_scope_nodes(mod: "_Module") -> List[ast.AST]:
    """Nodes at module scope: not inside any function, lambda or class
    (the bodies are not entered; computed once per module)."""
    cached = getattr(mod, "_scope_nodes", None)
    if cached is not None:
        return cached
    out: List[ast.AST] = []
    pending = list(ast.iter_child_nodes(mod.tree))
    while pending:
        node = pending.pop()
        out.append(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # The def or class itself binds its name here; its decorators,
            # defaults and bases are evaluated here too, its body is not.
            pending.extend(node.decorator_list)
            if not isinstance(node, ast.ClassDef):
                pending.extend(d for d in node.args.defaults + node.args.kw_defaults if d)
            continue
        if isinstance(node, ast.Lambda):
            continue
        pending.extend(ast.iter_child_nodes(node))
    mod._scope_nodes = out
    return out


def _own_scope_nodes(mod: "_Module", holder: ast.AST) -> List[ast.AST]:
    """Nodes in ``holder``'s own scope (a module, class or function): its
    statements, not entering nested functions, lambdas or classes (whose
    def/class node, decorators and defaults are included), plus a function's
    own parameters. Cached per holder."""
    cache = mod.__dict__.setdefault("_own_scope_cache", {})
    if id(holder) in cache:
        return cache[id(holder)]
    out: List[ast.AST] = []
    pending: List[ast.AST] = list(getattr(holder, "body", []))
    if isinstance(holder, (ast.FunctionDef, ast.AsyncFunctionDef)):
        pending.extend(ast.walk(holder.args))
    while pending:
        node = pending.pop()
        out.append(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            pending.extend(node.decorator_list)
            if not isinstance(node, ast.ClassDef):
                pending.extend(d for d in node.args.defaults + node.args.kw_defaults if d)
            continue
        if isinstance(node, ast.Lambda):
            continue
        pending.extend(ast.iter_child_nodes(node))
    cache[id(holder)] = out
    return out


def _bound_once_as(mod: "_Module", node: ast.AST) -> bool:
    """True when the def ``node`` is the ONLY binding of its name in its own
    scope (no second def under if/else, no later assignment, no import...)."""
    holder = _enclosing(mod, node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) or mod.tree
    sites = _binding_sites(
        _own_scope_nodes(mod, holder), node.name, mod.dotted, mod.rel.endswith("__init__.py")
    )
    return len(sites) == 1 and sites[0][1] is node


def _scope_bindings(mod: "_Module", scope: ast.AST, name: str) -> Tuple[set, bool, bool]:
    """:func:`_bindings` for a function's whole subtree, cached."""
    cache = mod.__dict__.setdefault("_binding_cache", {})
    key = (id(scope), name)
    if key not in cache:
        cache[key] = _bindings(
            ast.walk(scope), name, mod.dotted, mod.rel.endswith("__init__.py"), own=scope
        )
    return cache[key]


def _module_bindings(mod: "_Module", name: str) -> Tuple[set, bool, bool]:
    cache = mod.__dict__.setdefault("_module_binding_cache", {})
    if name not in cache:
        cache[name] = _bindings(
            _module_scope_nodes(mod), name, mod.dotted, mod.rel.endswith("__init__.py")
        )
    return cache[name]


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    return "?"


def _last_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _enclosing(mod: _Module, node: ast.AST, kinds) -> Optional[ast.AST]:
    current = mod.parents.get(id(node))
    while current is not None and not isinstance(current, kinds):
        current = mod.parents.get(id(current))
    return current


def _enclosing_function(mod: _Module, node: ast.AST) -> Optional[ast.AST]:
    return _enclosing(mod, node, (ast.FunctionDef, ast.AsyncFunctionDef))


def _defining_scope(mod: _Module, node: ast.AST) -> Optional[ast.AST]:
    """The function whose BODY ``node`` is in, for name resolution.

    A parameter's default, an annotation and a decorator are evaluated where
    the function is defined, not inside it, so a function reached through its
    ``args``, ``decorator_list`` or ``returns`` is skipped."""
    child = node
    current = mod.parents.get(id(node))
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if child is current.args or child is current.returns or child in current.decorator_list:
                child, current = current, mod.parents.get(id(current))
                continue
            return current
        child, current = current, mod.parents.get(id(current))
    return None


def _qualname(mod: _Module, func: ast.AST) -> str:
    names = [func.name]
    current = mod.parents.get(id(func))
    while current is not None:
        if isinstance(current, ast.ClassDef):
            names.append(current.name)
        elif isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(f"{current.name}.<locals>")
        current = mod.parents.get(id(current))
    return ".".join(reversed(names))


def _resolve(mod: _Module, func_node: ast.AST, at: ast.AST) -> Optional[str]:
    """The FINAL dotted name a call target refers to (re-exports inside the
    package followed, :func:`_final_identities`), or ``None`` when unknown
    or when it could stand for more than one thing."""
    found = _resolve_name(mod, func_node, at)
    if found is None:
        return None
    finals = _final_identities(mod, found)
    return next(iter(finals)) if len(finals) == 1 else None


def _resolve_name(mod: _Module, func_node: ast.AST, at: ast.AST) -> Optional[str]:
    """The dotted name a call target refers to, or ``None`` when unknown.

    A plain name resolves through the scopes that enclose ``at``: a function
    that binds it any way other than an import (a parameter, a default, an
    assignment, a loop, ``with`` or ``except`` target, a nested def, a
    ``global`` or ``nonlocal``) makes it unknown, and so does a module that
    both imports it and binds it otherwise, or imports it twice."""
    if isinstance(func_node, ast.Name):
        name = func_node.id
        scope = _defining_scope(mod, at)
        while scope is not None:
            imports, defined, other = _scope_bindings(mod, scope, name)
            if other or defined or len(imports) > 1:
                return None
            if imports:
                target = next(iter(imports))
                # Imported as anything else anywhere in the module: unknown.
                return target if mod.imports.get(name, set()) == {target} else None
            scope = _defining_scope(mod, scope)
        imports, defined, other = _module_bindings(mod, name)
        if other or (imports and defined) or len(imports) > 1:
            return None
        if defined:
            return None if name in mod.imports else f"{mod.dotted}.{name}"
        if not imports:
            return None
        target = next(iter(imports))
        # Imported as anything else anywhere in the module: unknown.
        return target if mod.imports.get(name, set()) == {target} else None
    if isinstance(func_node, ast.Attribute):
        value = func_node.value
        if isinstance(value, ast.Name) and value.id in ("self", "cls"):
            klass = _enclosing(mod, at, ast.ClassDef)
            if klass is not None:
                return f"{mod.dotted}.{klass.name}.{func_node.attr}"
            return None
        base = _resolve(mod, value, at)
        return f"{base}.{func_node.attr}" if base else None
    return None


def _name_is_shadowed(mod: _Module, at: ast.AST, name: str) -> bool:
    """True when a plain ``name`` is bound, other than by an import, in a
    function enclosing ``at`` or at module scope."""
    scope = _defining_scope(mod, at)
    while scope is not None:
        _, defined, other = _scope_bindings(mod, scope, name)
        if other or defined:
            return True
        scope = _defining_scope(mod, scope)
    return _module_bindings(mod, name)[2]


def _inline_helper(node: Optional[ast.AST], mod: _Module, wrappers: set, none_is_safe: bool = False) -> bool:
    """``node`` is a call to the helper (or to a function that only ever
    returns one) written right there, or ``None`` where that runs nothing."""
    if isinstance(node, ast.Constant) and node.value is None:
        return none_is_safe
    if isinstance(node, ast.Dict) and not node.keys:
        return True  # an empty environment, written inline, holds nothing
    if not isinstance(node, ast.Call):
        return False
    target = _resolve(mod, node.func, node)
    if isinstance(node.func, ast.Attribute) and target not in HELPERS and target != _FINISH:
        # Method dispatch (self.x(), obj.env()) is never trusted: only the
        # helper itself, or a module-level wrapper called by its plain name.
        return False
    if target == _FINISH:
        # It copies its input and adds to it: its input must be the helper's.
        given = node.args[0] if node.args else _env_keyword(node)
        return _inline_helper(given, mod, wrappers)
    return target in HELPERS or target in wrappers


def _single_use_helper_name(
    name: str, mod: _Module, func: ast.AST, wrappers: set, is_launch: Callable[[ast.Call], bool]
) -> bool:
    """``name`` is bound exactly once in ``func`` (by any binding form, see
    :func:`_names_bound_by`), by a single-target assignment of an inline helper
    call, is not declared global or nonlocal in an enclosing function, and
    every other use of it is as the ``env=`` keyword of a launch or
    generic-runner call in ``func`` itself."""
    sites = _binding_sites(ast.walk(func), name, mod.dotted, mod.rel.endswith("__init__.py"), own=func)
    if len(sites) != 1 or sites[0][0] != "name":
        return False
    stored = sites[0][1]
    statement = mod.parents.get(id(stored))
    if isinstance(statement, ast.Assign):
        if len(statement.targets) != 1 or statement.targets[0] is not stored:
            return False  # chained or unpacking assignment
    elif isinstance(statement, ast.AnnAssign):
        if statement.target is not stored or statement.value is None:
            return False
    else:
        return False  # augmented, walrus, loop, with, comprehension, del ...
    if not _inline_helper(statement.value, mod, wrappers):
        return False
    outer = _defining_scope(mod, func)
    while outer is not None:
        if any(
            kind == "declare"
            for kind, _n, _t in _binding_sites(
                ast.walk(outer), name, mod.dotted, mod.rel.endswith("__init__.py"), own=outer
            )
        ):
            return False
        outer = _defining_scope(mod, outer)
    for node in ast.walk(func):
        if not (isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load)):
            continue
        parent = mod.parents.get(id(node))
        if not (isinstance(parent, ast.keyword) and parent.arg == "env"):
            return False  # attribute, subscript, argument, return, alias ...
        call = mod.parents.get(id(parent))
        if not isinstance(call, ast.Call) or not is_launch(call):
            return False
        scope = mod.parents.get(id(call))
        while scope is not None and scope is not func:
            if isinstance(scope, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                return False  # captured by a closure
            scope = mod.parents.get(id(scope))
    return True


def _helper_shaped(
    node: Optional[ast.AST], mod: _Module, func: Optional[ast.AST], wrappers: set,
    none_is_safe: bool = False, is_launch: Optional[Callable[[ast.Call], bool]] = None,
) -> bool:
    """True when ``node`` (an ``env=`` value) is, provably, the helper's
    result: the helper called inline, or a name that holds nothing else and
    is used for nothing else (:func:`_single_use_helper_name`)."""
    if node is None:
        return False
    if _inline_helper(node, mod, wrappers, none_is_safe):
        return True
    if isinstance(node, ast.Name) and func is not None and is_launch is not None:
        return _single_use_helper_name(node.id, mod, func, wrappers, is_launch)
    return False


def _definition_counts(mod: _Module) -> Dict[str, int]:
    """How many definitions (def or class) each full qualified identity has
    across the whole module, nested paths included. Cached."""
    cached = getattr(mod, "_definition_counts", None)
    if cached is None:
        cached = {}
        for node in ast.walk(mod.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qual = _qualname(mod, node)
                cached[qual] = cached.get(qual, 0) + 1
        mod._definition_counts = cached
    return cached


def _trusted_definition(mod: _Module, node: ast.AST) -> bool:
    """A def the guard may rely on as a wrapper: a MODULE-LEVEL function
    (never a method, never nested), whose full qualified identity has exactly
    one definition in the module and which is the only binding of its name
    in the module's scope."""
    if not isinstance(mod.parents.get(id(node)), ast.Module):
        return False
    if _definition_counts(mod).get(_qualname(mod, node), 0) != 1:
        return False
    return _bound_once_as(mod, node)


def _wrappers(modules: List[_Module]) -> set:
    """Functions whose whole body (after a docstring) is one ``return`` of an
    inline helper call, by dotted name."""
    found: set = set()
    changed = True
    while changed:
        changed = False
        for mod in modules:
            for node in ast.walk(mod.tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                full = f"{mod.dotted}.{_qualname(mod, node)}"
                if full in found:
                    continue
                body = list(node.body)
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)
                ):
                    body = body[1:]  # a leading docstring
                # Exactly one statement, ``return <helper call>``: nothing can
                # fall through to an implicit None (which would inherit).
                if (
                    not node.decorator_list  # a decorator could turn a refusal into None
                    and _trusted_definition(mod, node)  # module level, defined once
                    and len(body) == 1
                    and isinstance(body[0], ast.Return)
                    and isinstance(body[0].value, ast.Call)
                    and _inline_helper(body[0].value, mod, found)
                ):
                    found.add(full)
                    changed = True
    return found


def _possible_targets(mod: _Module, node: ast.AST) -> set:
    """Every dotted name a plain or dotted name can stand for, through every
    import of its root anywhere in the module, each followed to its final
    identity through re-exports inside the package."""
    if isinstance(node, ast.Name):
        return _final_targets(mod, mod.imports.get(node.id, ()))
    if isinstance(node, ast.Attribute):
        return _final_targets(
            mod, {f"{base}.{node.attr}" for base in _possible_targets(mod, node.value)}
        )
    return set()


#: Calls that load code by a name or a file chosen at run time.
_DYNAMIC_IMPORTS = {
    "importlib.import_module", "importlib.__import__", "builtins.__import__",
    "importlib.util.module_from_spec", "importlib.util.spec_from_file_location",
}
#: Names that reach the import machinery without being imported.
_DYNAMIC_IMPORT_NAMES = {"__import__": "builtins.__import__", "__builtins__": "__builtins__"}


def _dynamic_import(mod: _Module, call: ast.AST) -> Optional[str]:
    """Which dynamic import ``call`` is (``importlib.import_module``,
    ``__import__``, ``importlib.util.module_from_spec`` ...), or ``None``."""
    if not isinstance(call, ast.Call):
        return None
    if isinstance(call.func, ast.Name) and call.func.id == "__import__":
        return "builtins.__import__"
    for target in sorted(_possible_targets(mod, call.func)):
        if target in _DYNAMIC_IMPORTS:
            return target
    return None


def _dynamic_import_problem(mod: _Module, call: ast.Call) -> Optional[str]:
    """Every dynamic import is a violation outside :data:`MODULE_USE_ALLOWED`
    (14 October 2026), whatever its argument: what it loads, and so what it
    launches, is not in the source this guard reads."""
    kind = _dynamic_import(mod, call)
    if kind is None:
        return None
    return (
        f"a dynamic import ({kind}) loads code this guard cannot read, so what it "
        f"launches cannot be checked; import it statically"
    )


def _dynamic_import_held(mod: _Module, node: ast.AST) -> Optional[str]:
    """Why ``node`` reaches the import machinery other than by a call to a
    dynamic import (a dynamic import function held, passed or stored, or
    ``__builtins__`` used at all), or ``None``."""
    if isinstance(node, ast.Name) and node.id == "__builtins__":
        return "__builtins__ is used, which reaches the import machinery this guard cannot read"
    parent = mod.parents.get(id(node))
    if isinstance(parent, ast.Call) and parent.func is node:
        return None  # a call: judged as a dynamic import itself
    if isinstance(node, ast.Name) and node.id in _DYNAMIC_IMPORT_NAMES:
        found = _DYNAMIC_IMPORT_NAMES[node.id]
    else:
        hits = sorted(t for t in _possible_targets(mod, node) if t in _DYNAMIC_IMPORTS)
        found = hits[0] if hits else None
    if found is None:
        return None
    return (
        f"the dynamic import {found} is used other than by calling it (held, passed "
        f"or stored), so what it loads cannot be checked"
    )


_MODULE_SPECS: Dict[str, bool] = {}


def _is_module_identity(mod: _Module, dotted: str) -> bool:
    """``dotted`` names a module: one of the scanned package's, or one that
    is importable outside it (``importlib.util.find_spec``, cached)."""
    if _UNFOLLOWED in dotted:
        return False
    if dotted in mod.index:
        return True
    if dotted.split(".")[0] == mod.root:
        return False
    if dotted not in _MODULE_SPECS:
        import importlib.util

        try:
            _MODULE_SPECS[dotted] = importlib.util.find_spec(dotted) is not None
        except Exception:  # noqa: BLE001 - not a module (or not importable)
            _MODULE_SPECS[dotted] = False
    return _MODULE_SPECS[dotted]


def _visible_import_targets(mod: _Module, node: ast.Name) -> set:
    """Everything the plain name ``node`` could hold through an import:
    every import binding of it (from the single binding enumerator) in each
    function enclosing ``node``, in each class enclosing it, at module scope,
    and anywhere a ``global`` declaration makes a function's import a module
    binding, each followed to its final identity. Another binding of the same
    name (a later ``name = None``, a parameter, a conditional rebinding) never
    removes these: the name may still hold the import when it is used."""
    name = node.id
    targets: set = set()
    scope = _defining_scope(mod, node)
    while scope is not None:
        targets |= _scope_bindings(mod, scope, name)[0]
        scope = _defining_scope(mod, scope)
    klass = _enclosing(mod, node, ast.ClassDef)
    is_package = mod.rel.endswith("__init__.py")
    while klass is not None:
        targets |= {
            target
            for kind, _site, target in _binding_sites(
                _own_scope_nodes(mod, klass), name, mod.dotted, is_package
            )
            if kind == "import"
        }
        klass = _enclosing(mod, klass, ast.ClassDef)
    targets |= _module_bindings(mod, name)[0]
    declared = mod.__dict__.get("_global_names")
    if declared is None:
        declared = {
            g for n in ast.walk(mod.tree) if isinstance(n, ast.Global) for g in n.names
        }
        mod._global_names = declared
    if name in declared:
        targets |= set(mod.imports.get(name, ()))
    return _final_targets(mod, targets)


def _module_used_as_value(mod: _Module, node: ast.AST) -> Optional[str]:
    """Why a loaded name or attribute chain that names a module (any module:
    the package's own, the standard library's or another) is used other
    than as the base of an attribute (stored, passed, returned, defaulted,
    put in a container ...), or ``None``: what is reached through a held
    module cannot be checked."""
    parent = mod.parents.get(id(node))
    if isinstance(parent, ast.Attribute) and parent.value is node:
        return None
    if isinstance(parent, ast.Call) and parent.func is node:
        return None  # calling a module fails by itself
    # A name counts when ANY import binding it can see is a module, whatever
    # else also binds it: shadowing never exempts a value use.
    targets = (
        _visible_import_targets(mod, node) if isinstance(node, ast.Name)
        else _possible_targets(mod, node)
    )
    for target in sorted(targets):
        if _is_module_identity(mod, target):
            return (
                f"the module {_dotted(node)} ({target}) is used other than as the base "
                f"of an attribute (held, passed, returned, defaulted or stored), so what "
                f"is reached through it cannot be checked"
            )
    return None


def _launch_kind(mod: _Module, node: ast.AST) -> Optional[str]:
    """What launch ``node`` (a call target or a value) names, if any."""
    if isinstance(node, ast.Attribute) and node.attr in _ANY_RECEIVER_LAUNCHES:
        return _dotted(node)
    for target in sorted(_possible_targets(mod, node)):
        if _is_launch_target(target):
            return target
        if _UNFOLLOWED in target:
            # Called itself, or a launch name called on it: it could be a
            # launch, so its env= must be the helper's.
            head, _, tail = target.partition(_UNFOLLOWED)
            if not tail or tail.rsplit(".", 1)[-1] in LAUNCH_NAMES:
                return f"{head}{tail} (a re-export the guard cannot follow)"
    return None


def _factory_literal(call: ast.Call) -> bool:
    """The launch runs one of the factory's own programs, provably.

    Only when (a) the command is a list or tuple literal written inline in
    this call, (b) its first item is the literal "git", "docker", "pgrep" or
    "ps", and (c) the call has no ``executable=``, no ``shell=`` other than a
    literal False, and no ``*`` or ``**`` unpacked arguments. A named
    command, a module-level constant or anything built elsewhere never
    qualifies: such a launch uses a helper-built environment, or is on the
    allowed list with a reason.
    """
    if len(call.args) > 1 or any(isinstance(a, ast.Starred) for a in call.args):
        return False  # a further positional argument can be the executable or shell
    for kw in call.keywords:
        if kw.arg is None or kw.arg == "executable":
            return False
        if kw.arg == "shell" and not (
            isinstance(kw.value, ast.Constant) and kw.value.value is False
        ):
            return False
    node = _first_argument(call)
    return (
        isinstance(node, (ast.List, ast.Tuple))
        and bool(node.elts)
        and isinstance(node.elts[0], ast.Constant)
        and isinstance(node.elts[0].value, str)
        and node.elts[0].value in FACTORY_PROGRAMS
    )


def _env_keyword(call: ast.Call, position: Optional[int] = None) -> Optional[ast.AST]:
    for kw in call.keywords:
        if kw.arg == "env":
            return kw.value
    if position is not None and len(call.args) > position:
        return call.args[position]
    return None


def _annotation_nodes(tree: ast.AST) -> set:
    """Nodes inside type annotations: naming ``subprocess.Popen`` as a type
    launches nothing."""
    found: set = set()
    roots: List[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and node.annotation is not None:
            roots.append(node.annotation)
        elif isinstance(node, ast.AnnAssign):
            roots.append(node.annotation)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is not None:
            roots.append(node.returns)
    for root in roots:
        found.update(id(n) for n in ast.walk(root))
    return found


def _first_argument(call: ast.Call) -> Optional[ast.AST]:
    if call.args:
        return call.args[0]
    for kw in call.keywords:
        if kw.arg in ("args", "argv", "command", "cmd"):
            return kw.value
    return None


#: How each generic runner takes an environment, derived from its own def
#: (14 October 2026), never written by hand: (kind, position, named), where
#: kind is "positional" (``env`` at ``position`` among the arguments a caller
#: passes, after ``self``/``cls`` for a method), "keyword" (keyword-only
#: ``env``), "kwargs" (no ``env`` parameter, but ``**kwargs`` may carry one),
#: "varargs" (no ``env`` parameter, but ``*args`` past the ``named``
#: positional parameters may) or "none" (it cannot be given one at all).
_RUNNER_ENV: Dict[Tuple[str, str], Tuple[str, Optional[int], int]] = {}


def _runner_source(rel: str) -> Path:
    """The source file a GENERIC_RUNNERS entry names: in this repository's
    package, or in GuardKit's for a ``guardkit:`` entry."""
    if rel.startswith("guardkit:"):
        import importlib.util

        spec = importlib.util.find_spec("guardkit")
        assert spec is not None and spec.submodule_search_locations, "GuardKit is not importable"
        return Path(next(iter(spec.submodule_search_locations))) / rel[len("guardkit:"):]
    return PACKAGE / rel


def _runner_env(rel: str, fname: str) -> Tuple[str, Optional[int], int]:
    """How the runner ``fname`` in ``rel`` takes an environment, read from
    its own def (every def of that name in the file must agree)."""
    key = (rel, fname)
    if key not in _RUNNER_ENV:
        tree = ast.parse(_runner_source(rel).read_text(encoding="utf-8"))
        methods = {
            id(item)
            for klass in ast.walk(tree) if isinstance(klass, ast.ClassDef)
            for item in klass.body
        }
        found = set()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != fname:
                continue
            args = node.args
            positional = [a.arg for a in args.posonlyargs + args.args]
            is_static = any(_last_name(d) == "staticmethod" for d in node.decorator_list)
            if id(node) in methods and not is_static:
                positional = positional[1:]  # self or cls: not passed by the caller
            if "env" in positional:
                found.add(("positional", positional.index("env"), len(positional)))
            elif any(a.arg == "env" for a in args.kwonlyargs):
                found.add(("keyword", None, len(positional)))
            elif args.kwarg is not None:
                found.add(("kwargs", None, len(positional)))
            elif args.vararg is not None:
                found.add(("varargs", None, len(positional)))
            else:
                found.add(("none", None, len(positional)))
        assert len(found) == 1, f"{rel}:{fname}: no single signature: {sorted(found, key=str)}"
        _RUNNER_ENV[key] = found.pop()
    return _RUNNER_ENV[key]


def _runner_identity(package_name: str, rel: str, fname: str) -> str:
    """The dotted name a generic runner is imported by."""
    if rel.startswith("guardkit:"):
        package_name, rel = "guardkit", rel[len("guardkit:"):]
    parts = [package_name, *Path(rel).with_suffix("").parts]
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join([*parts, fname])


def _runner_call_matches(
    call: ast.Call, spec: Dict[str, Any], mod: Optional[_Module] = None,
    identity: Optional[str] = None,
) -> bool:
    """A call to a generic runner: by what it resolves to (an imported alias
    included), by its last name (any object or module spelling), or by a
    dotted suffix for the generic method names."""
    if mod is not None and identity is not None and _resolve(mod, call.func, call) == identity:
        return True
    if _last_name(call.func) in spec.get("names", ()):
        # A plain name bound locally (a parameter, an assignment ...) is not
        # the runner, whatever it is called.
        if mod is not None and isinstance(call.func, ast.Name) and _name_is_shadowed(
            mod, call, call.func.id
        ):
            return False
        return True
    dotted = _callee_name(call)
    return any(dotted.endswith(suffix) for suffix in spec.get("suffixes", ()))


def _callee_name(call: ast.Call) -> str:
    return _dotted(call.func)


#: Generic method names a runner may have that are ordinary words elsewhere;
#: those runners are found by a dotted suffix, so the bare word is not reserved.
_ORDINARY_RUNNER_WORDS = {"run", "execute", "_run", "runner"}


def _reserved_names() -> set:
    """Names that may never be rebound: the helper's, and every generic
    runner's (outside the ordinary words above)."""
    reserved = {target.rsplit(".", 1)[1] for target in HELPERS}
    for (rel, fname), spec in GENERIC_RUNNERS.items():
        if fname not in _ORDINARY_RUNNER_WORDS:
            reserved.add(fname)
        if not spec.get("scope"):
            reserved.update(n for n in spec.get("names", ()) if n not in _ORDINARY_RUNNER_WORDS)
    return reserved


def _reserved_name_rebindings(modules: List[_Module]) -> List[str]:
    """Every rebinding of a reserved name: a parameter, a local binding, a
    nested def, a ``global``/``nonlocal``, or a module-level rebinding of the
    helper's, a generic runner's or a launch function's name (an imported
    alias of one included). Imports, and a module-level def or class that is
    not also imported, are not rebindings."""
    base = _reserved_names()
    problems: List[str] = []
    for mod in modules:
        reserved = set(base)
        for alias, targets in mod.imports.items():
            for target in _final_targets(mod, targets):
                module, _, last = target.rpartition(".")
                if last in base or target in HELPERS or _is_launch_target(target):
                    reserved.add(alias)

        def flag(node: ast.AST, name: str, how: str) -> None:
            holder = _enclosing(mod, node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            where = getattr(holder, "name", "<module>")
            problems.append(
                f"{mod.rel}:{getattr(node, 'lineno', 0)} in {where}: the reserved name "
                f"{name!r} (the helper's, a generic runner's or a launch function's) is "
                f"rebound {how}"
            )

        is_package = mod.rel.endswith("__init__.py")
        how_by_kind = {
            "param": "as a parameter",
            "except": "by an except target",
            "declare": "by a global or nonlocal declaration",
            "match": "by a match-case capture",
        }
        for node in ast.walk(mod.tree):
            in_function = _enclosing(mod, node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) is not None
            for name, kind, _target in _names_bound_by(node, mod.dotted, is_package):
                if name not in reserved or kind == "import":
                    continue
                if kind == "def":
                    if in_function:
                        flag(node, name, "by a nested definition")
                    elif name in mod.imports and _enclosing(mod, node, ast.ClassDef) is None:
                        flag(node, name, "by a definition of an imported name")
                elif kind == "name":
                    flag(node, name, "by an assignment or target" if in_function else "at module level")
                else:
                    flag(node, name, how_by_kind[kind])
    return problems


def _guarded_names(mod: _Module, runner_ids: set) -> Dict[str, str]:
    """The names in ``mod`` that are guarded, by their own spelling: a launch
    module (kind ``module``), and a launch function, a generic runner or the
    helper (kind ``function``), whether imported (in any scope) or, for a
    runner, defined at module level here."""
    guarded: Dict[str, str] = {}
    for name, targets in mod.imports.items():
        for target in _final_targets(mod, targets):
            module, _, last = target.rpartition(".")
            # Only the guarded name's own spelling: any other spelling is an
            # alias, which is a violation in itself (_aliased_guarded_imports).
            if name == last and (
                _is_launch_target(target) or target in runner_ids or target in HELPERS
            ):
                guarded[name] = "function"
            elif _is_launch_module(target) and (
                name == target.split(".")[0]  # import subprocess / os / asyncio ...
                or name == last  # a launch submodule: from asyncio import subprocess
            ):
                guarded.setdefault(name, "module")
    for node in mod.tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and f"{mod.dotted}.{node.name}" in runner_ids:
            guarded.setdefault(node.name, "function")
    return guarded


_LAUNCH_BEARING: Dict[str, bool] = {}


def _is_launch_bearing_module(dotted: str) -> bool:
    """A launch module, or a real submodule of one, that itself defines at
    least one launch name (found by importing it and looking; cached):
    subprocess, os, asyncio, asyncio.subprocess, multiprocessing.popen_fork;
    never os.path."""
    if not _is_launch_module(dotted):
        return False
    if dotted not in _LAUNCH_BEARING:
        import importlib

        try:
            module = importlib.import_module(dotted)
            _LAUNCH_BEARING[dotted] = any(
                hasattr(module, name) and not _is_not_launch(f"{dotted}.{name}")
                for name in LAUNCH_NAMES
            )
        except Exception:  # noqa: BLE001 - unknown means "treat as launch-bearing"
            _LAUNCH_BEARING[dotted] = True
    return _LAUNCH_BEARING[dotted]


def _is_not_launch(dotted: str) -> bool:
    return dotted in NOT_LAUNCHES


def _launch_attribute_names() -> set:
    return set(LAUNCH_NAMES)


def _indirect_use(mod: _Module, node: ast.Name, kind: str) -> Optional[str]:
    """Why a load of a guarded name is not a direct use, or ``None``.

    A function, runner or helper may only be called: the name is the
    ``func`` of a call. A module may only be the base of an attribute
    (``subprocess.run``, ``os.environ``); when that attribute chain names a
    launch function, the chain itself must be the ``func`` of a call."""
    parent = mod.parents.get(id(node))
    if kind == "function":
        if isinstance(parent, ast.Call) and parent.func is node:
            return None
        return (
            f"{node.id} is used other than by calling it (held, passed, returned, "
            f"stored or wrapped), so what it launches cannot be checked"
        )
    if not (isinstance(parent, ast.Attribute) and parent.value is node):
        return (
            f"the launch module {node.id} is used other than through its "
            f"attributes (held, passed, returned or stored), so what it launches "
            f"cannot be checked"
        )
    chain = parent
    launch_attr = any(_is_launch_target(t) for t in _possible_targets(mod, chain))
    while True:
        above = mod.parents.get(id(chain))
        if isinstance(above, ast.Attribute) and above.value is chain:
            chain = above
            launch_attr = launch_attr or any(
                _is_launch_target(t) for t in _possible_targets(mod, chain)
            )
            continue
        break
    if launch_attr and not (isinstance(above, ast.Call) and above.func is chain):
        if id(chain) in _annotation_nodes_cache(mod):
            return None
        return (
            f"the launch function {_dotted(chain)} is used other than by calling it, "
            f"so its env= cannot be checked"
        )
    # The whole chain names a launch-bearing submodule (it was not the base of
    # a further attribute): held, passed or stored, it could be called
    # through later (backend = multiprocessing.popen_fork; backend.Popen(...)).
    if any(_is_launch_bearing_module(t) for t in _possible_targets(mod, chain)):
        if id(chain) in _annotation_nodes_cache(mod):
            return None
        return (
            f"the launch-bearing module {_dotted(chain)} is used other than as the "
            f"base of an attribute, so what is launched through it cannot be checked"
        )
    return None


def _annotation_nodes_cache(mod: _Module) -> set:
    cached = getattr(mod, "_annotation_ids", None)
    if cached is None:
        cached = _annotation_nodes(mod.tree)
        mod._annotation_ids = cached
    return cached


#: Launch and runner names that are ordinary words elsewhere (``from x
#: import run as y`` is common and unrelated): the module-blind alias check
#: leaves them to the resolved-identity check.
_GENERIC_GUARDED_WORDS = {
    "run", "call", "system", "popen", "fork", "spawn", "execute", "_run", "runner",
}


def _distinctive_guarded_names(runner_ids: set) -> set:
    """The last components of guarded names that are not ordinary words."""
    names = {target.rsplit(".", 1)[1] for target in HELPERS}
    names.update(identity.rsplit(".", 1)[1] for identity in runner_ids)
    names.update(_launch_attribute_names())
    return names - _GENERIC_GUARDED_WORDS


def _aliased_guarded_imports(modules: List[_Module], runner_ids: set) -> List[str]:
    """A guarded name (a launch module or function, a generic runner, the
    helper) imported under another local name is a violation in itself:
    every guarded name is only ever used under its own spelling."""
    problems: List[str] = []
    distinctive = _distinctive_guarded_names(runner_ids)
    for mod in modules:
        for node in ast.walk(mod.tree):
            aliased: List[str] = []
            if isinstance(node, ast.Import):
                aliased = [
                    f"{a.name} as {a.asname}" for a in node.names
                    if a.asname and a.asname != a.name
                    and _is_launch_module(a.name)
                ]
            elif isinstance(node, ast.ImportFrom):
                # One resolver for every identity: relative levels included.
                bindings = _import_bindings(node, mod.dotted, mod.rel.endswith("__init__.py"))
                for alias, (_bound, target) in zip(node.names, bindings):
                    if not alias.asname or alias.asname == alias.name:
                        continue
                    # What the import finally names, through re-exports.
                    finals = _final_identities(mod, target) | {target}
                    if any(
                        _is_launch_target(final)
                        or _is_launch_module(final)  # from asyncio import subprocess as x
                        or final in runner_ids
                        or final in HELPERS
                        for final in finals
                    ) or (
                        # Belt and braces: a distinctive guarded name is never
                        # aliased, whatever module text it comes from.
                        alias.name in distinctive
                    ):
                        aliased.append(f"{target} as {alias.asname}")
            for what in aliased:
                holder = _enclosing(mod, node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                problems.append(
                    f"{mod.rel}:{node.lineno} in {getattr(holder, 'name', '<module>')}: "
                    f"a guarded name (a launch module or function, a generic runner or "
                    f"the helper) is imported under another name ({what}); import it "
                    f"under its own name"
                )
    return problems


def _attribute_used_as_value(mod: _Module, node: ast.Attribute, runner_ids: set) -> Optional[str]:
    """Why a loaded attribute chain is used as a value, or ``None``.

    Judged on EVERY attribute, whatever its root, by what it finally names
    (component by component, re-exports inside the package followed, see
    :func:`_possible_targets`): a launch function, a generic runner or the
    helper may only be the ``func`` of a call; a launch-bearing module may
    only be called through or be the base of a further attribute; a chain
    that could not be followed and ends in a launch name may only be called.
    Held, stored, passed or returned, what it launches could not be checked."""
    parent = mod.parents.get(id(node))
    if isinstance(parent, ast.Call) and parent.func is node:
        return None
    is_base = isinstance(parent, ast.Attribute) and parent.value is node
    for target in sorted(_possible_targets(mod, node)):
        if _UNFOLLOWED in target:
            if target.replace(_UNFOLLOWED, "").rsplit(".", 1)[-1] in LAUNCH_NAMES:
                return (
                    f"{_dotted(node)} could be the launch "
                    f"{target.replace(_UNFOLLOWED, '')} (a re-export the guard cannot "
                    f"follow) and is used other than by calling it, so its env= cannot "
                    f"be checked"
                )
            continue
        if _is_launch_target(target) or target in runner_ids or target in HELPERS:
            return (
                f"{_dotted(node)} is {target}, used other than by calling it (held, "
                f"passed, returned, stored or wrapped), so what it launches cannot be "
                f"checked"
            )
        if _is_launch_bearing_module(target) and not is_base:
            return (
                f"{_dotted(node)} is the launch-bearing module {target}, used other "
                f"than as the base of an attribute, so what is launched through it "
                f"cannot be checked"
            )
    return None


def _launch_named_modules(modules: List[_Module]) -> List[str]:
    """No module or package inside the scanned package may be named like a
    launch module (``subprocess``, ``os``, ``asyncio``, ``pty``,
    ``multiprocessing``, ``posix``, ``nt``): the guard reads those names as
    the standard library's."""
    problems: List[str] = []
    for mod in modules:
        named = [part for part in Path(mod.rel).with_suffix("").parts if part in LAUNCH_MODULES]
        if named:
            problems.append(
                f"{mod.rel}:1 in <module>: a module or package of this package is named "
                f"{named[0]}, like the launch module; rename it"
            )
    return problems


def _init_submodule_collisions(modules: List[_Module]) -> List[str]:
    """A package's ``__init__`` may not bind a name that is also one of its
    own submodules or subpackages, except by importing that submodule itself
    (``from . import sub``, ``from package import sub``, ``import
    package.sub``) or a name from that same submodule (``from .sub import
    sub``, which the guard follows through the submodule as a second
    possible identity, see :func:`_follow`). Anything else (an import from
    elsewhere, a def, a class, an assignment) makes what the name gives
    depend on import order, so the guard could judge the wrong one."""
    problems: List[str] = []
    for mod in modules:
        if not mod.rel.endswith("__init__.py"):
            continue
        depth = mod.dotted.count(".") + 1
        subs = {
            dotted.rsplit(".", 1)[1]
            for dotted in mod.index
            if dotted.startswith(mod.dotted + ".") and dotted.count(".") == depth
        }
        for sub in sorted(subs):
            own = f"{mod.dotted}.{sub}"
            lines = [
                getattr(node, "lineno", 1)
                for kind, node, target in _binding_sites(
                    _module_scope_nodes(mod), sub, mod.dotted, True
                )
                if not (kind == "import" and (target == own or target.startswith(own + ".")))
            ]
            lines += [
                node.lineno
                for node in ast.walk(mod.tree)
                if isinstance(node, (ast.Global, ast.Nonlocal)) and sub in node.names
            ]
            for line in sorted(set(lines)):
                problems.append(
                    f"{mod.rel}:{line} in <module>: the package binds {sub}, which is "
                    f"also its own submodule, other than by importing that submodule or a "
                    f"name from it; "
                    f"use another name"
                )
    return problems


def unaccounted_launches(package: Path) -> List[str]:
    modules = _load_modules(package)
    wrappers = _wrappers(modules)
    problems: List[str] = []
    runner_ids = {
        _runner_identity(package.name, rel, fname) for rel, fname in GENERIC_RUNNERS
    }
    # Method-style runners (``x._run_recorded``) by name; plainly named ones
    # such as ``runner`` in one file are left to their scoped call check.
    runner_attrs = {
        name
        for spec in GENERIC_RUNNERS.values()
        if not spec.get("scope")
        for name in spec.get("names", ())
    }

    runner_specs = [
        (spec, _runner_identity(package.name, rel, fname))
        for (rel, fname), spec in GENERIC_RUNNERS.items()
    ]

    def launch_checker(mod: _Module) -> Callable[[ast.Call], bool]:
        def is_launch(call: ast.Call) -> bool:
            if _launch_kind(mod, call.func):
                return True
            return any(
                (not spec.get("scope") or mod.rel in spec["scope"])
                and _runner_call_matches(call, spec, mod, identity)
                for spec, identity in runner_specs
            )

        return is_launch

    def place(mod: _Module, node: ast.AST) -> Tuple[Optional[ast.AST], str]:
        func = _enclosing_function(mod, node)
        named = _enclosing(mod, node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        return func, getattr(named, "name", "<module>")

    def judge(
        mod: _Module, call: ast.Call, what: str, *, default_is_safe=False,
        none_is_safe=False, runner_env: Optional[Tuple[str, Optional[int], int]] = None,
    ) -> None:
        """Judge a launch (``runner_env`` None) or a generic runner call.

        Unpacking (``*args`` or ``**kwargs``) is refused unless the runner
        cannot take an environment at all; an environment passed
        positionally is judged exactly like ``env=``; and "env omitted is
        safe" holds only when it is provably omitted."""
        func, fname = place(mod, call)
        if (mod.rel, fname) in ALLOWED:
            return
        if _factory_literal(call):
            return
        kind, position, named = runner_env or ("launch", None, 0)
        unpacked = any(isinstance(a, ast.Starred) for a in call.args) or any(
            kw.arg is None for kw in call.keywords
        )
        if unpacked and kind != "none":
            problems.append(
                f"{mod.rel}:{call.lineno} in {fname}: {what}: *args or **kwargs "
                f"unpacking could carry an environment the guard cannot see"
            )
            return
        if kind == "varargs" and len(call.args) > named:
            problems.append(
                f"{mod.rel}:{call.lineno} in {fname}: {what}: extra positional "
                f"arguments reach *args, which could carry an environment"
            )
            return
        env = _env_keyword(call, position if kind == "positional" else None)
        if env is None and default_is_safe:
            return  # provably omitted: no env=, no argument at its place, no unpacking
        if _helper_shaped(env, mod, func, wrappers, none_is_safe, launch_checker(mod)):
            return
        reason = "no env= (it inherits everything)" if env is None else "env= is not the helper's"
        problems.append(f"{mod.rel}:{call.lineno} in {fname}: {what}: {reason}")

    for mod in modules:
        annotations = _annotation_nodes(mod.tree)
        guarded = _guarded_names(mod, runner_ids)
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.Call):
                kind = _launch_kind(mod, node.func)
                if kind:
                    judge(mod, node, f"process launch {kind}")
                problem = _dynamic_import_problem(mod, node)
                if problem:
                    _, fname = place(mod, node)
                    # Only MODULE_USE_ALLOWED waives it: an entry in ALLOWED
                    # (for a launch) says nothing about loading code.
                    if (mod.rel, fname) not in MODULE_USE_ALLOWED:
                        problems.append(f"{mod.rel}:{node.lineno} in {fname}: {problem}")
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in guarded:
                if id(node) in annotations:
                    continue  # a type annotation launches nothing
                problem = _indirect_use(mod, node, guarded[node.id])
                if problem:
                    _, fname = place(mod, node)
                    if (mod.rel, fname) not in ALLOWED:
                        problems.append(f"{mod.rel}:{node.lineno} in {fname}: {problem}")
            elif (
                isinstance(node, ast.Attribute)
                and isinstance(node.ctx, ast.Load)
                and node.attr in runner_attrs
                and id(node) not in annotations
            ):
                parent = mod.parents.get(id(node))
                if not (isinstance(parent, ast.Call) and parent.func is node):
                    _, fname = place(mod, node)
                    if (mod.rel, fname) not in ALLOWED:
                        problems.append(
                            f"{mod.rel}:{node.lineno} in {fname}: the generic runner "
                            f"{_dotted(node)} is used other than by calling it, so its "
                            f"env= cannot be checked"
                        )
    problems.extend(_reserved_name_rebindings(modules))
    problems.extend(_aliased_guarded_imports(modules, runner_ids))
    problems.extend(_launch_named_modules(modules))
    problems.extend(_init_submodule_collisions(modules))
    for mod in modules:
        annotations = _annotation_nodes_cache(mod)
        for node in ast.walk(mod.tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.ctx, ast.Load)
                and id(node) not in annotations
            ):
                problem = _attribute_used_as_value(mod, node, runner_ids)
                if problem:
                    _, fname = place(mod, node)
                    if (mod.rel, fname) not in ALLOWED:
                        problems.append(f"{mod.rel}:{node.lineno} in {fname}: {problem}")
            # Any module object, only ever as an attribute base.
            if (
                isinstance(node, (ast.Name, ast.Attribute))
                and isinstance(node.ctx, ast.Load)
                and id(node) not in annotations
            ):
                for problem in (_module_used_as_value(mod, node), _dynamic_import_held(mod, node)):
                    if problem:
                        _, fname = place(mod, node)
                        if (mod.rel, fname) not in MODULE_USE_ALLOWED:
                            problems.append(f"{mod.rel}:{node.lineno} in {fname}: {problem}")
    for mod in modules:
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
                problems.append(
                    f"{mod.rel}:{node.lineno} in <module>: a wildcard import "
                    f"(from {'.' * node.level}{node.module or ''} import *) binds names "
                    f"the guard cannot see; import names explicitly"
                )
    for (rel, fname), spec in GENERIC_RUNNERS.items():
        identity = _runner_identity(package.name, rel, fname)
        for mod in modules:
            if spec.get("scope") and mod.rel not in spec["scope"]:
                continue
            for node in ast.walk(mod.tree):
                if not isinstance(node, ast.Call) or not _runner_call_matches(
                    node, spec, mod, identity
                ):
                    continue
                func = _enclosing_function(mod, node)
                if mod.rel == rel and getattr(func, "name", None) == fname:
                    continue  # the runner's own body
                judge(
                    mod, node, f"call to the generic runner {fname}",
                    default_is_safe=spec.get("default_is_safe", False),
                    none_is_safe=spec.get("none_is_safe", False),
                    runner_env=_runner_env(rel, fname),
                )
    return sorted(set(problems))


#: The coach's probes (13 October 2026): each ``vNN`` function must be named.
GUARD_PROBES = textwrap.dedent(
    '''\
    import asyncio
    import functools
    import os
    import subprocess
    from guardkit.orchestrator import process_group
    from guardkit.orchestrator.process_group import run_in_own_group
    from guardkit.orchestrator.project_command_env import project_command_environment
    from guardkit.orchestrator.project_command_env import project_command_environment as pce_alias


    def _project_env():  # the same name as a real wrapper elsewhere
        return dict(os.environ)


    def v01_name_collision(cmd):
        subprocess.run(cmd, shell=True, env=_project_env())


    def v02_mutated_after_helper(cmd, wf):
        env = project_command_environment(wf, None)
        env.update(os.environ)
        subprocess.run(cmd, shell=True, env=env)


    def v03_runner_by_reference(cmd):
        runner = subprocess.run
        runner(cmd, shell=True)


    def v04_partial(cmd):
        functools.partial(subprocess.run, shell=True)(cmd)


    async def v05_loop_method(cmd):
        loop = asyncio.get_running_loop()
        await loop.subprocess_shell(asyncio.SubprocessProtocol, cmd)


    async def v06_nested_attribute(cmd):
        await asyncio.subprocess.create_subprocess_shell(cmd)


    def v07_qualified_generic_runner(cmd):
        process_group.run_in_own_group(cmd, shell=True, cwd=".", env=dict(os.environ), timeout=5)


    def v08_plain_generic_runner(cmd):
        run_in_own_group(cmd, shell=True, cwd=".", env=dict(os.environ), timeout=5)


    def v09_other_object_run_recorded(validator, cmd):
        validator._run_recorded(cmd, evidence=("x", ".", None), shell=True, env=os.environ.copy())


    def v10_getattr(cmd):
        getattr(subprocess, "run")(cmd, shell=True)


    def v11_env_item_injected(cmd, wf):
        env = project_command_environment(wf, None)
        env["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]
        subprocess.run(cmd, shell=True, env=env)


    def v12_empty_dict_then_filled(cmd):
        env = {}
        env.update(os.environ)
        subprocess.run(cmd, shell=True, env=env)


    def _copy_everything():
        out = {}
        for k, v in os.environ.items():
            out[k] = v
        return out


    def v13_wrapper_built_from_empty(cmd):
        subprocess.run(cmd, shell=True, env=_copy_everything())


    def v14_existing_unrelated_wrapper_name(cmd, answer):
        subprocess.run(cmd, shell=True, env=parse_answer(answer))


    def v15_plain(cmd):
        subprocess.run(cmd, shell=True)


    def _widen(env):
        env.update(os.environ)


    def v18_widened_through_an_alias(cmd, wf):
        env = project_command_environment(wf, None)
        other = env
        other.update(os.environ)
        subprocess.run(cmd, shell=True, env=env)


    def v19_handed_to_a_function_first(cmd, wf):
        env = project_command_environment(wf, None)
        _widen(env)
        subprocess.run(cmd, shell=True, env=env)


    def v20_dunder_import(cmd):
        __import__("subprocess").run(cmd, shell=True)


    class v21_PopenSubclass(subprocess.Popen):
        pass


    from guardkit.orchestrator.process_group import run_in_own_group as launch
    from guardkit.orchestrator.project_command_env import finish_project_environment


    def v22_generic_runner_under_an_alias(cmd):
        launch(cmd, cwd=".", env=dict(os.environ), timeout=5)


    def v23_finish_on_the_factory_environment(cmd):
        subprocess.run(cmd, shell=True, env=finish_project_environment(dict(os.environ)))


    def ok_finish(cmd, wf):
        env = finish_project_environment(project_command_environment(wf, None), additions={"X": "1"})
        subprocess.run(cmd, shell=True, env=env)


    from guardkit.orchestrator.process_group import run_project_command


    def v24_generic_runner_held_in_a_variable(cmd):
        invoke = run_project_command
        invoke(cmd, shell=True, env=dict(os.environ))


    def v25_generic_runner_partially_applied(cmd):
        functools.partial(run_project_command, shell=True)(cmd, env=dict(os.environ))


    def ok_runner(cmd, wf):
        run_project_command(cmd, shell=True, env=project_command_environment(wf, None))


    OK_ARGV = ("git", "status")
    MUTABLE_ARGV = ["git", "status"]


    def _swap(argv):
        argv[0] = "sh"


    def v26_command_list_item_replaced(cmd):
        argv = ["git", "-c", "x"]
        argv[0] = "sh"
        subprocess.run(argv)


    def v27_command_list_slice_replaced(cmd):
        argv = ["git", "x"]
        argv[:1] = ["sh"]
        subprocess.run(argv)


    def v28_command_list_changed_through_an_alias(cmd):
        argv = ["git", "x"]
        other = argv
        other[0] = "sh"
        subprocess.run(argv)


    def v29_command_list_handed_to_a_call_first(cmd):
        argv = ["git", "x"]
        _swap(argv)
        subprocess.run(argv)


    def v30_command_list_inserted_into(cmd):
        argv = ["git", "x"]
        argv.insert(0, "sh")
        subprocess.run(argv)


    def v31_module_level_list_command(cmd):
        subprocess.run(MUTABLE_ARGV)


    def v32_command_list_assigned_twice(cmd, other):
        argv = ["git", "x"]
        argv = other
        subprocess.run(argv)


    def v33_chained_assignment_alias(cmd):
        argv = other = ["git", "-c", "x"]
        other[0] = "sh"
        subprocess.run(argv)


    def v34_executable_override(cmd):
        subprocess.run(["git", "-c", "x"], executable="/bin/sh")


    def v35_shell_true(cmd):
        subprocess.run(["git", "status"], shell=True)


    def v36_keyword_unpacking(cmd, options):
        subprocess.run(["git", "status"], **options)


    def v37_positional_unpacking(cmd, rest):
        subprocess.run(["git", "status"], *rest)


    def v38_named_list(cmd):
        argv = ["git", "status"]
        subprocess.run(argv)


    def v39_module_tuple(cmd):
        subprocess.run(list(OK_ARGV))


    def v40_positional_executable(cmd):
        subprocess.Popen(["git", "-c", "x"], -1, "/bin/sh")


    def v41_positional_shell(cmd):
        subprocess.Popen(["git", "status"], -1, None, None, None, None, None, True, True)


    def v42_chained_env_alias(cmd, wf):
        env = other = project_command_environment(wf, None)
        other.update(os.environ)
        subprocess.run(cmd, env=env)


    def v43_tuple_unpacked_env(cmd, wf):
        env, other = project_command_environment(wf, None), None
        subprocess.run(cmd, env=env)


    def v44_env_handed_to_a_logger(cmd, wf, log):
        env = project_command_environment(wf, None)
        log.info("env %s", env)
        subprocess.run(cmd, env=env)


    def v45_env_returned(cmd, wf):
        env = project_command_environment(wf, None)
        subprocess.run(cmd, env=env)
        return env


    def _falls_through_on_error(wf):
        try:
            return project_command_environment(wf, None)
        except OSError:
            pass


    def _returns_only_sometimes(wf, ready):
        if ready:
            return project_command_environment(wf, None)


    def _does_something_first(wf):
        os.environ["OPENAI_API_KEY"] = "x"
        return project_command_environment(wf, None)


    def _single_return_wrapper(wf):
        """A docstring is fine."""
        return project_command_environment(wf, None, additions={"X": "1"})


    def v46_wrapper_falls_through_on_error(cmd, wf):
        subprocess.run(cmd, shell=True, env=_falls_through_on_error(wf))


    def v47_wrapper_returns_only_sometimes(cmd, wf):
        subprocess.run(cmd, shell=True, env=_returns_only_sometimes(wf, True))


    def v48_wrapper_does_something_first(cmd, wf):
        subprocess.run(cmd, shell=True, env=_does_something_first(wf))


    def _swallow(fn):
        def inner(*a, **k):
            try:
                return fn(*a, **k)
            except OSError:
                return None
        return inner


    @_swallow
    def _decorated_wrapper(wf):
        return project_command_environment(wf, None)


    def v49_decorated_wrapper(cmd, wf):
        subprocess.run(cmd, shell=True, env=_decorated_wrapper(wf))


    def v50_parameter_default_shadows_the_helper(
        cmd, wf, project_command_environment=lambda *a: dict(os.environ)
    ):
        subprocess.run(cmd, shell=True, env=project_command_environment(wf, None))


    def v51_local_reassignment_shadows_the_helper(cmd, wf):
        project_command_environment = lambda *a: dict(os.environ)  # noqa: E731
        subprocess.run(cmd, shell=True, env=project_command_environment(wf, None))


    def v52_for_target_shadows_the_helper(cmd, wf, makers):
        for project_command_environment in makers:
            subprocess.run(cmd, shell=True, env=project_command_environment(wf, None))


    def v54_same_named_default_capture(cmd, run_project_command=run_project_command):
        return run_project_command(cmd, shell=True, env=None, timeout=5)


    def v55_differently_named_default_capture(cmd, go=run_project_command):
        return go(cmd, shell=True, env=None, timeout=5)


    def v56_lambda_default_calling_a_runner(
        cmd, go=lambda c: run_project_command(c, shell=True, env=None, timeout=5)
    ):
        return go(cmd)


    def v57_local_named_like_the_helper(cmd, wf):
        finish_project_environment = lambda e: dict(os.environ)  # noqa: E731
        subprocess.run(cmd, shell=True, env=finish_project_environment(None))


    def v58_from_import_rebinds_env(cmd, wf):
        env = project_command_environment(wf, None)
        from os import environ as env
        subprocess.run(cmd, env=env)


    def v59_import_rebinds_env(cmd, wf):
        env = project_command_environment(wf, None)
        import os as env
        subprocess.run(cmd, env=env)


    def v60_class_rebinds_env(cmd, wf):
        env = project_command_environment(wf, None)

        class env(dict):
            pass

        subprocess.run(cmd, env=env)


    def v61_def_rebinds_env(cmd, wf):
        env = project_command_environment(wf, None)

        def env():
            return dict(os.environ)

        subprocess.run(cmd, env=env)


    def v62_match_capture_rebinds_env(cmd, wf):
        env = project_command_environment(wf, None)
        match dict(os.environ):
            case env:
                pass
        subprocess.run(cmd, env=env)


    def v63_del_then_reassign_env(cmd, wf):
        env = project_command_environment(wf, None)
        del env
        env = dict(os.environ)
        subprocess.run(cmd, env=env)


    def v64_module_alias_reused_elsewhere(cmd):
        import subprocess as tool
        tool.run(cmd, shell=True)


    def _other_tool_user(text):
        import json as tool
        return tool.loads(text)


    def v65_function_alias_reused_elsewhere(cmd):
        from subprocess import run as go
        go(cmd, shell=True)


    def _other_go_user(text):
        from json import loads as go
        return go(text)


    def ok_helper_env_beside_reused_names(cmd, wf):
        import json as tool
        subprocess.run(tool.loads(cmd), env=project_command_environment(wf, None))


    def v67_runner_alias_in_one_scope(cmd):
        from guardkit.orchestrator.process_group import run_project_command as invoke
        invoke(cmd, shell=True, env=None)


    def _other_invoke(text):
        from json import loads as invoke
        return invoke(text)


    def v68_module_assigned_to_a_variable(cmd):
        process_tool = subprocess
        process_tool.run(cmd, shell=True)


    def v69_module_passed_as_an_argument(cmd, use):
        use(subprocess, cmd)


    def v70_module_as_a_default(cmd, sp_module=subprocess):
        sp_module.run(cmd, shell=True)


    def v71_launch_function_stored_in_a_dict(cmd):
        table = {"go": subprocess.run}
        table["go"](cmd, shell=True)


    def v72_launch_function_stored_in_a_list(cmd):
        table = [subprocess.Popen]
        table[0](cmd, shell=True)


    def v73_runner_returned_from_a_function():
        return run_project_command


    def v74_relative_runner_alias_assigned(cmd):
        from .process_group import run_project_command as invoke
        dispatch = invoke
        dispatch(cmd, shell=True, env=None)


    def v75_relative_plugin_runner_alias_assigned(cmd):
        from ..bdd.plugin import run_project_command as invoke_plugin
        dispatch = invoke_plugin
        dispatch(cmd, shell=True, env=None)


    def v76_relative_alias_reused_in_unrelated_scopes(cmd):
        from .process_group import run_in_own_group as starter
        starter(cmd, cwd=".", env=dict(os.environ), timeout=5)


    def _unrelated_starter(text):
        from json import loads as starter
        return starter(text)


    def v77_parent_relative_alias(cmd):
        from ..orchestrator.process_group import run_project_command as go_relative
        go_relative(cmd, shell=True, env=None)


    def ok_unaliased_relative_import_with_helper_env(cmd, wf):
        from .process_group import run_project_command
        run_project_command(cmd, shell=True, env=project_command_environment(wf, None))


    if os.environ.get("PROBE_CHOICE"):
        def _maybe_wrapper(wf):
            return project_command_environment(wf, None)
    else:
        def _maybe_wrapper(wf):
            return dict(os.environ)


    def v78_conditional_safe_and_unsafe_definitions(cmd, wf):
        subprocess.run(cmd, shell=True, env=_maybe_wrapper(wf))


    def _twice_wrapper(wf):
        return project_command_environment(wf, None)


    def _twice_wrapper(wf):  # noqa: F811
        return dict(os.environ)


    def v79_duplicate_plain_definitions(cmd, wf):
        subprocess.run(cmd, shell=True, env=_twice_wrapper(wf))


    def _rebound_wrapper(wf):
        return project_command_environment(wf, None)


    _rebound_wrapper = lambda wf: dict(os.environ)  # noqa: E731


    def v80_definition_rebound_by_assignment(cmd, wf):
        subprocess.run(cmd, shell=True, env=_rebound_wrapper(wf))


    class _TwiceMethods:
        def _env(self, wf):
            return project_command_environment(wf, None)

        def _env(self, wf):  # noqa: F811
            return dict(os.environ)

        def v81_duplicate_method_definitions(self, cmd, wf):
            subprocess.run(cmd, shell=True, env=self._env(wf))


    if os.environ.get("PROBE_CLASS"):
        class _Commands:
            def command_env(self, wf):
                return project_command_environment(wf, None)

            def v82_conditional_duplicate_classes(self, cmd, wf):
                subprocess.run(cmd, shell=True, env=self.command_env(wf))
    else:
        class _Commands:
            def command_env(self, wf):
                return dict(os.environ)

            def v82_conditional_duplicate_classes(self, cmd, wf):
                subprocess.run(cmd, shell=True, env=self.command_env(wf))


    class _PlainTwice:
        def command_env(self, wf):
            return project_command_environment(wf, None)

        def v83_duplicate_plain_classes(self, cmd, wf):
            subprocess.run(cmd, shell=True, env=self.command_env(wf))


    class _PlainTwice:  # noqa: F811
        def command_env(self, wf):
            return dict(os.environ)

        def v83_duplicate_plain_classes(self, cmd, wf):
            subprocess.run(cmd, shell=True, env=self.command_env(wf))


    class _ReboundClass:
        def command_env(self, wf):
            return project_command_environment(wf, None)

        def v84_class_rebound_by_assignment(self, cmd, wf):
            subprocess.run(cmd, shell=True, env=self.command_env(wf))


    _ReboundClass = dict  # noqa: F811


    def _outer_twice():
        def _inner_env(wf):
            return project_command_environment(wf, None)

        def v85_nested_under_a_duplicated_outer(cmd, wf):
            subprocess.run(cmd, shell=True, env=_inner_env(wf))

        return v85_nested_under_a_duplicated_outer


    def _outer_twice():  # noqa: F811
        def _inner_env(wf):
            return dict(os.environ)

        def v85_nested_under_a_duplicated_outer(cmd, wf):
            subprocess.run(cmd, shell=True, env=_inner_env(wf))

        return v85_nested_under_a_duplicated_outer


    class _BaseCommands:
        def command_env(self, wf):
            return project_command_environment(wf, None)

        def v86_subclass_overrides_the_wrapper(self, cmd, wf):
            subprocess.run(cmd, shell=True, env=self.command_env(wf))


    class _UnsafeCommands(_BaseCommands):
        def command_env(self, wf):
            return dict(os.environ)


    class _SingleCommands:
        def command_env(self, wf):
            return project_command_environment(wf, None)

        def v91_plain_method_wrapper_via_self(self, cmd, wf):
            subprocess.run(cmd, shell=True, env=self.command_env(wf))


    class _CondBase:
        def command_env(self, wf):
            return project_command_environment(wf, None)

        def v90_conditional_subclass_override(self, cmd, wf):
            subprocess.run(cmd, shell=True, env=self.command_env(wf))


    class _CondChild(_CondBase):
        if os.environ.get("PROBE_OVERRIDE"):
            def command_env(self, wf):
                return dict(os.environ)


    async def v92_bare_create_subprocess_shell(cmd):
        from asyncio.subprocess import create_subprocess_shell
        await create_subprocess_shell(cmd)


    async def v93_bare_create_subprocess_exec(cmd):
        from asyncio.subprocess import create_subprocess_exec
        await create_subprocess_exec(cmd)


    def v94_bare_os_system(cmd):
        from os import system
        system(cmd)


    def v95_bare_pty_spawn(cmd):
        from pty import spawn
        spawn(cmd)


    async def v96_bare_asyncio_create_subprocess_exec(cmd):
        from asyncio import create_subprocess_exec
        await create_subprocess_exec(cmd)


    async def ok_bare_create_subprocess_shell_with_helper_env(cmd, wf):
        from asyncio.subprocess import create_subprocess_shell
        await create_subprocess_shell(cmd, env=project_command_environment(wf, None))


    async def ok_bare_create_subprocess_exec_with_helper_env(cmd, wf):
        from asyncio import create_subprocess_exec
        await create_subprocess_exec(cmd, env=project_command_environment(wf, None))


    def v97_deep_launch_held_in_a_variable(process_object):
        import multiprocessing.popen_fork
        launch = multiprocessing.popen_fork.Popen
        launch(process_object)


    def v98_deep_asyncio_launch_held_in_a_variable(cmd):
        f = asyncio.subprocess.create_subprocess_exec
        return f(cmd)


    def ok_module_attribute_that_is_not_a_launch(cmd):
        return os.path.join(cmd, "a")


    def v133_module_attribute_that_is_a_module_stored(cmd):
        x = os.path
        return x.join(cmd, "a")


    async def ok_direct_deep_call_with_helper_env(cmd, wf):
        await asyncio.subprocess.create_subprocess_exec(
            cmd, env=project_command_environment(wf, None)
        )


    def v99_launch_bearing_submodule_stored(process_object):
        import multiprocessing.popen_fork
        backend = multiprocessing.popen_fork
        backend.Popen(process_object)


    async def v100_asyncio_subprocess_stored(cmd):
        m = asyncio.subprocess
        await m.create_subprocess_exec(cmd)


    def v101_subprocess_module_stored(cmd):
        s = subprocess
        s.run(cmd, shell=True)


    async def ok_direct_dotted_call_through_a_submodule(cmd, wf):
        await asyncio.subprocess.create_subprocess_shell(
            cmd, env=project_command_environment(wf, None)
        )


    def ok_asyncio_run_is_not_a_launch(coroutine):
        return asyncio.run(coroutine)


    def ok_bare_os_getenv_is_not_a_module(cmd, wf):
        from os import getenv
        if getenv("PROBE_FLAG"):
            subprocess.run(cmd, shell=True, env=project_command_environment(wf, None))


    def ok_direct_subprocess_run_with_helper_env(cmd, wf):
        subprocess.run(cmd, shell=True, env=project_command_environment(wf, None))


    def ok_direct_runner_with_helper_env(cmd, wf):
        run_project_command(cmd, shell=True, env=project_command_environment(wf, None))


    def ok_os_path_and_environ(cmd):
        return os.path.join(cmd, os.environ.get("HOME", ""))


    def ok_unshadowed_alias(cmd, wf):
        subprocess.run(cmd, shell=True, env=pce_alias(wf, None))


    def ok_single_return_wrapper(cmd, wf):
        subprocess.run(cmd, shell=True, env=_single_return_wrapper(wf))


    def ok_single_use_named_env(cmd, wf):
        env = project_command_environment(wf, None)
        subprocess.run(cmd, shell=True, env=env)


    def ok_inline_env(cmd, wf):
        subprocess.run(cmd, shell=True, env=project_command_environment(wf, None))


    def ok_git_inline_no_env(cmd):
        subprocess.run(["git", "status"], shell=False)


    def ok_git_inline_with_helper(cmd, wf):
        subprocess.run(("git", "status"), env=project_command_environment(wf, None))


    def v16_empty_dict_item_filled(cmd):
        env = {}
        env["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]
        subprocess.run(cmd, shell=True, env=env)


    def v17_or_assigned(cmd, wf):
        env = project_command_environment(wf, None)
        env |= dict(os.environ)
        subprocess.run(cmd, shell=True, env=env)


    def ok_helper(cmd, wf):
        env = project_command_environment(wf, None)
        subprocess.run(cmd, shell=True, env=env)


    def ok_git(cmd):
        subprocess.run(["git", "status"])


    def ok_wrapper(cmd, wf):
        subprocess.run(cmd, shell=True, env=_real_wrapper(wf))


    def _real_wrapper(wf):
        return project_command_environment(wf, None, additions={"X": "1"})
    '''
)


#: Wildcard imports, one module each: the import itself is the violation.
GUARD_PROBES_WILDCARD = {
    "zz_wild_subprocess.py": "from subprocess import *  # noqa: F403\n\n\ndef w_run(cmd):\n    run(cmd, shell=True)  # noqa: F405\n",
    "zz_wild_os.py": "from os import *  # noqa: F403\n\n\ndef w_system(cmd):\n    system(cmd)  # noqa: F405\n",
    "zz_wild_json.py": "from json import *  # noqa: F403\n\n\ndef w_loads(text):\n    return loads(text)  # noqa: F405\n",
}


#: A module that imports the helper and then rebinds its name.
GUARD_PROBES_REBOUND = textwrap.dedent(
    '''\
    import os
    import subprocess
    from guardkit.orchestrator.project_command_env import project_command_environment

    import subprocess as launcher

    project_command_environment = lambda *a: dict(os.environ)  # noqa: E731


    def _reuses_the_alias(text):
        import json as launcher
        return launcher.loads(text)


    def v66_module_alias_reused_in_a_function(cmd):
        launcher.run(cmd, shell=True)


    def v53_module_level_rebinding(cmd, wf):
        subprocess.run(cmd, shell=True, env=project_command_environment(wf, None))
    '''
)


#: Launches re-exported through other modules of the package (14 October
#: 2026): each module's file name -> its text; ``__PKG__`` becomes the probe
#: package's name. ``zz_reexport_missing`` is deliberately absent.
GUARD_PROBES_REEXPORT = {
    "zz_reexport_api.py": "from subprocess import run\n",
    "zz_reexport_alias_api.py": "from subprocess import Popen as P\n",
    "zz_reexport_runner_api.py": (
        "from guardkit.orchestrator.process_group import run_in_own_group\n"
    ),
    "zz_reexport_hop1.py": "from subprocess import check_output\n",
    "zz_reexport_hop2.py": "from .zz_reexport_hop1 import check_output\n",
    "zz_reexport_cycle_a.py": "from .zz_reexport_cycle_b import spawn_it\n",
    "zz_reexport_cycle_b.py": "from .zz_reexport_cycle_a import spawn_it\n",
    "zz_reexport_fallback.py": (
        "try:\n"
        "    from subprocess import check_call\n"
        "except ImportError:  # pragma: no cover\n"
        "    check_call = None\n"
    ),
    "zz_reexport_util.py": (
        "LIMIT = 5\n\n\n"
        "def describe(value):\n    return str(value)\n\n\n"
        "def _make():\n    return print\n\n\n"
        "made_runner = _make()\n"
    ),
    "zz_reexport_modapi.py": "import subprocess\n",
    # A launch reached through a package module's attribute and used as a
    # value (14 October 2026).
    "zz_attr_consumer.py": textwrap.dedent(
        '''\
        from guardkit.orchestrator.project_command_env import project_command_environment

        from . import zz_plain
        from . import zz_reexport_api
        from . import zz_reexport_fallback
        from . import zz_reexport_modapi
        from . import zz_reexport_util
        from .zz_plain import run as plain_run


        def v117_reexported_launch_stored_through_a_module_attribute(cmd):
            invoke = zz_reexport_api.run
            return invoke(cmd, shell=True)


        def v118_unfollowed_launch_name_stored_through_a_module_attribute(cmd):
            held = zz_reexport_fallback.check_call
            return held(cmd, shell=True)


        def v119_reexported_launch_passed_through_a_module_attribute(cmd):
            return [zz_reexport_api.run]


        def v120_reexported_launch_module_stored_through_a_module_attribute(cmd):
            launcher = zz_reexport_modapi.subprocess
            return launcher.run(cmd, shell=True)


        def ok_direct_reexport_attribute_call_with_helper_env(cmd, wf):
            return zz_reexport_api.run(cmd, shell=True, env=project_command_environment(wf, None))


        def ok_harmless_package_attributes_as_values():
            limit = zz_reexport_util.LIMIT
            describe = zz_reexport_util.describe
            return describe(limit)


        def ok_genuine_submodule_and_self_import_as_values():
            go = zz_plain.run.go
            return go(), plain_run.go(), zz_plain.other.go(), zz_plain.third.go()
        '''
    ),
    # The two blunt collision rules: a package binding a name that is also
    # its submodule (a launch, a launch module, an ordinary function), and a
    # module named like a launch module. zz_plain only imports its own
    # submodules: allowed.
    "zz_collide/__init__.py": "from subprocess import run\n",
    "zz_collide/run.py": "",
    "zz_shadow/__init__.py": "import subprocess\n",
    "zz_shadow/subprocess.py": "",
    "zz_noncollide/__init__.py": "from json import loads\n",
    "zz_noncollide/loads.py": "",
    "zz_plain/__init__.py": (
        "from . import run\n"
        "from __PKG__.orchestrator.zz_plain import other\n"
        "import __PKG__.orchestrator.zz_plain.third\n"
    ),
    "zz_plain/run.py": "def go():\n    return 1\n",
    "zz_plain/other.py": "def go():\n    return 2\n",
    "zz_plain/third.py": "def go():\n    return 3\n",
    # The allowed idiom: a package importing a name from its same-named
    # submodule; followed, so a launch re-exported this way is still seen.
    "zz_fromsub/__init__.py": "from .run import run\n",
    "zz_fromsub/run.py": "from subprocess import run\n",
    "zz_fromsub_ok/__init__.py": "from .resolve import resolve\n",
    "zz_fromsub_ok/resolve.py": "def resolve(value):\n    return value\n",
    "zz_fromsub_consumer.py": textwrap.dedent(
        '''\
        from guardkit.orchestrator.project_command_env import project_command_environment

        from .zz_fromsub import run
        from .zz_fromsub_ok import resolve


        def v121_launch_imported_from_the_same_named_submodule(cmd):
            return run(cmd, shell=True)


        def v122_launch_imported_from_the_same_named_submodule_stored(cmd):
            held = run
            return held(cmd, shell=True)


        def ok_same_named_submodule_launch_with_helper_env(cmd, wf):
            return run(cmd, shell=True, env=project_command_environment(wf, None))


        def ok_name_imported_from_the_same_named_submodule(value):
            held = resolve
            return held(value)
        '''
    ),
    "zz_collide_consumer.py": textwrap.dedent(
        '''\
        from . import zz_collide
        from .zz_collide import run


        def collide_called(cmd):
            return run(cmd, shell=True)


        def collide_stored(cmd):
            held = run
            return held(cmd, shell=True)


        def collide_by_attribute(cmd):
            return zz_collide.run(cmd, shell=True)
        '''
    ),
    # Module objects only ever as attribute bases; dynamic imports only by a
    # literal non-launch name used as an attribute base (14 October 2026).
    "zz_modvalue_consumer.py": textwrap.dedent(
        '''\
        import importlib
        import importlib.util
        import json

        from guardkit.orchestrator.project_command_env import project_command_environment

        from . import zz_reexport_api
        from . import zz_reexport_util


        def _takes(module):
            return module


        def v123_package_module_stored_then_called_through(cmd):
            api = zz_reexport_api
            return api.run(cmd, shell=True)


        def v124_standard_library_module_stored():
            j = json
            return j.dumps({})


        def v125_package_module_passed_to_a_function():
            return _takes(zz_reexport_api)


        def v126_package_module_as_a_default(cmd, module=zz_reexport_api):
            return module.run(cmd, shell=True)


        def v127_module_in_a_container():
            return {"serialiser": json}


        def v128_dynamic_import_of_a_launch_module(cmd):
            return importlib.import_module("subprocess").run(cmd)


        def v129_dynamic_import_of_a_name_held_in_a_variable(name):
            return importlib.import_module(name)


        def v130_dynamic_import_of_a_literal_stored():
            loaded = __import__("json")
            return loaded.dumps({})


        def v131_dynamic_import_of_a_package_module_that_re_exports_a_launch(cmd):
            return importlib.import_module("__PKG__.orchestrator.zz_reexport_api").run(
                cmd, shell=True
            )


        def v132_module_loaded_from_a_spec(spec):
            return importlib.util.module_from_spec(spec).value


        def ok_direct_reexport_call_with_helper_env(cmd, wf):
            return zz_reexport_api.run(cmd, shell=True, env=project_command_environment(wf, None))


        def ok_module_attribute_use():
            return json.dumps({"a": 1})


        def v138_literal_dynamic_import_outside_the_list():
            return importlib.import_module("json").dumps({"a": 1})


        def v139_literal_dynamic_import_reaching_a_re_export_through_a_longer_chain(cmd):
            return importlib.import_module("__PKG__.orchestrator").zz_reexport_api.run(
                cmd, shell=True
            )


        def v140_dynamic_import_function_held():
            loader = importlib.import_module
            return loader("json")


        def v141_builtin_import_held():
            loader = __import__
            return loader("json")


        def v142_builtins_reached_directly():
            return __builtins__


        def ok_static_import_as_an_attribute_base():
            return zz_reexport_util.describe(zz_reexport_util.LIMIT)
        '''
    ),
    # A held module whose name is then rebound: any import binding counts.
    "zz_rebind_consumer.py": textwrap.dedent(
        '''\
        def v134_module_held_then_its_name_rebound(cmd):
            from . import zz_reexport_api
            api = zz_reexport_api
            zz_reexport_api = None
            return api.run(cmd, shell=True)


        def v135_name_rebound_before_the_module_is_held(cmd):
            zz_reexport_api = None
            from . import zz_reexport_api
            api = zz_reexport_api
            return api.run(cmd, shell=True)


        def v136_name_rebound_conditionally(cmd, flag):
            from . import zz_reexport_api
            if flag:
                zz_reexport_api = None
            api = zz_reexport_api
            return api.run(cmd, shell=True)


        def v137_launch_held_then_its_name_rebound(cmd):
            from subprocess import check_call
            held = check_call
            check_call = None
            return held(cmd, shell=True)


        def ok_name_bound_only_to_values_used_as_a_value(flag, zz_reexport_util=None):
            # Same spelling as a package module, but never imported here.
            settings = {"a": 1}
            if flag:
                settings = None
            return settings, zz_reexport_util
        '''
    ),
    # Where a runner's environment really goes: positional, unpacked.
    "zz_runner_args_consumer.py": textwrap.dedent(
        '''\
        import os
        import subprocess

        from guardkit.orchestrator.completion_verification import run_completion_verification
        from guardkit.orchestrator.process_group import run_project_command
        from guardkit.orchestrator.project_command_env import project_command_environment


        def v143_env_passed_positionally_to_a_default_safe_runner(root, cmd):
            return run_completion_verification(root, cmd, "declared", None, 5, dict(os.environ))


        def v144_env_in_unpacked_keywords_to_a_default_safe_runner(root, cmd):
            options = {"env": dict(os.environ)}
            return run_completion_verification(root, cmd, "declared", None, 5, **options)


        def v145_unpacked_args_reaching_the_env_position(root, cmd):
            rest = ("declared", None, 5, dict(os.environ))
            return run_completion_verification(root, cmd, *rest)


        def v146_unpacked_keywords_to_a_keyword_only_runner(cmd, wf):
            options = {"env": dict(os.environ)}
            return run_project_command(cmd, **options)


        def v147_unpacked_keywords_to_a_launch(cmd, wf):
            options = {"env": project_command_environment(wf, None)}
            return subprocess.run(cmd, **options)


        def ok_env_omitted_on_a_default_safe_runner(root, cmd):
            return run_completion_verification(root, cmd, "declared", None, 5)


        def ok_helper_env_by_keyword(root, cmd, wf):
            return run_completion_verification(
                root, cmd, "declared", None, 5, env=project_command_environment(wf, None)
            )


        def ok_helper_env_positionally(root, cmd, wf):
            return run_completion_verification(
                root, cmd, "declared", None, 5, project_command_environment(wf, None)
            )
        '''
    ),
    "zz_reexport_consumer.py": textwrap.dedent(
        '''\
        import __PKG__.orchestrator.zz_reexport_api
        import __PKG__.orchestrator.zz_reexport_api as api_module
        from guardkit.orchestrator.project_command_env import project_command_environment

        from . import zz_reexport_hop2
        from .zz_reexport_alias_api import P
        from .zz_reexport_api import run
        from .zz_reexport_cycle_a import spawn_it
        from .zz_reexport_fallback import check_call
        from .zz_reexport_hop2 import check_output
        from .zz_reexport_missing import start_it
        from .zz_reexport_runner_api import run_in_own_group
        from .zz_reexport_util import LIMIT, describe, made_runner


        def v102_reexported_subprocess_run(cmd):
            return run(cmd, shell=True)


        def v103_reexported_aliased_popen(cmd):
            return P(cmd)


        def v104_reexported_generic_runner(cmd):
            return run_in_own_group(cmd, shell=True)


        def v105_two_hop_reexport(cmd):
            return check_output(cmd, shell=True)


        def v106_two_hop_reexport_through_the_module(cmd):
            return zz_reexport_hop2.check_output(cmd, shell=True)


        def v107_reexport_through_an_aliased_package_import(cmd):
            return api_module.run(cmd, shell=True)


        def v108_reexport_through_the_full_dotted_name(cmd):
            return __PKG__.orchestrator.zz_reexport_api.run(cmd, shell=True)


        def v109_cyclic_reexport(cmd):
            return spawn_it(cmd)


        def v110_reexport_with_a_fallback_binding(cmd):
            return check_call(cmd, shell=True)


        def v111_reexport_with_a_fallback_binding_held(cmd):
            held = check_call
            return held(cmd, shell=True)


        def v112_reexport_from_a_missing_module(cmd):
            return start_it(cmd)


        def ok_reexported_run_with_helper_env(cmd, wf):
            return run(cmd, shell=True, env=project_command_environment(wf, None))


        def ok_reexported_package_function(value):
            return describe(value)


        def ok_reexported_constant_read():
            return LIMIT + 1


        def ok_reexported_assigned_name(value):
            # One plain assignment ends the chain: storing a launch in a name
            # is already flagged where it is stored.
            return made_runner(value)
        '''
    ),
}


def _probe_package(tmp_path: Path, name: str) -> Path:
    pkg = tmp_path / name
    (pkg / "orchestrator").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "orchestrator" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "orchestrator" / "zz_probe.py").write_text(GUARD_PROBES, encoding="utf-8")
    (pkg / "orchestrator" / "zz_rebound.py").write_text(GUARD_PROBES_REBOUND, encoding="utf-8")
    for filename, text in GUARD_PROBES_WILDCARD.items():
        (pkg / "orchestrator" / filename).write_text(text, encoding="utf-8")
    for filename, text in GUARD_PROBES_REEXPORT.items():
        (pkg / "orchestrator" / filename).parent.mkdir(parents=True, exist_ok=True)
        (pkg / "orchestrator" / filename).write_text(
            text.replace("__PKG__", name), encoding="utf-8"
        )
    return pkg


def test_the_guard_catches_every_probe(tmp_path: Path) -> None:
    """Synthetic source fed to the guard (never added to the package)."""
    problems = unaccounted_launches(_probe_package(tmp_path, PACKAGE.name))
    named = {p.split(" in ", 1)[1].split(":", 1)[0] for p in problems}
    expected = {
        n.name
        for text in [GUARD_PROBES, GUARD_PROBES_REBOUND, *GUARD_PROBES_REEXPORT.values()]
        for n in ast.walk(ast.parse(text))
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name.startswith("v")
    }
    assert expected - named == set(), f"slipped past the guard: {sorted(expected - named)}"
    for filename in GUARD_PROBES_WILDCARD:
        assert any(
            f"orchestrator/{filename}:1 in <module>: a wildcard import" in p for p in problems
        ), filename
    # The reserved-name rule itself, not only the checks it backs up.
    reserved_hits = {
        p.split(" in ", 1)[1].split(":", 1)[0] for p in problems if "the reserved name" in p
    }
    assert {
        "v51_local_reassignment_shadows_the_helper",
        "v54_same_named_default_capture",
        "v57_local_named_like_the_helper",
    } <= reserved_hits, reserved_hits
    assert any(
        "zz_rebound.py" in p and "the reserved name" in p and "at module level" in p
        for p in problems
    ), problems
    assert not {
        "ok_helper", "ok_git", "ok_wrapper", "ok_finish", "ok_runner",
        "ok_git_inline_no_env", "ok_git_inline_with_helper",
        "ok_single_use_named_env", "ok_inline_env", "ok_single_return_wrapper",
        "ok_unshadowed_alias", "ok_helper_env_beside_reused_names",
        "ok_direct_subprocess_run_with_helper_env", "ok_direct_runner_with_helper_env",
        "ok_os_path_and_environ", "ok_unaliased_relative_import_with_helper_env",
        "ok_bare_create_subprocess_shell_with_helper_env",
        "ok_bare_create_subprocess_exec_with_helper_env",
        "ok_asyncio_run_is_not_a_launch", "ok_bare_os_getenv_is_not_a_module",
        "ok_module_attribute_that_is_not_a_launch", "ok_direct_deep_call_with_helper_env",
        "ok_direct_dotted_call_through_a_submodule",
        "ok_reexported_run_with_helper_env", "ok_reexported_package_function",
        "ok_reexported_constant_read", "ok_reexported_assigned_name",
        "ok_direct_reexport_attribute_call_with_helper_env",
        "ok_harmless_package_attributes_as_values",
        "ok_genuine_submodule_and_self_import_as_values",
        "ok_same_named_submodule_launch_with_helper_env",
        "ok_name_imported_from_the_same_named_submodule",
        "ok_direct_reexport_call_with_helper_env", "ok_module_attribute_use",
        "ok_static_import_as_an_attribute_base",
        "ok_env_omitted_on_a_default_safe_runner", "ok_helper_env_by_keyword",
        "ok_helper_env_positionally",
        "ok_name_bound_only_to_values_used_as_a_value",
    } & named, problems
    # The collision rules: each package that binds its own submodule's name,
    # and the module named like a launch module; never the self-imports.
    for where, what in [
        ("zz_collide/__init__.py:1", "the package binds run"),
        ("zz_shadow/__init__.py:1", "the package binds subprocess"),
        ("zz_noncollide/__init__.py:1", "the package binds loads"),
        ("zz_shadow/subprocess.py:1", "named subprocess, like the launch module"),
    ]:
        assert any(f"orchestrator/{where} in <module>: " in p and what in p for p in problems), (
            where, problems,
        )
    assert not [
        p for p in problems
        if "zz_plain" in p or "zz_fromsub_ok" in p or "zz_fromsub/__init__.py" in p
    ], problems
    # The exporter that renames a launch is itself an alias violation.
    assert any(
        "zz_reexport_alias_api.py:1 in <module>: a guarded name" in p for p in problems
    ), problems


def test_every_process_launch_is_accounted_for() -> None:
    problems = unaccounted_launches(PACKAGE)
    assert not problems, (
        "These process launches neither build their environment with "
        "GuardKit's project_command_env, nor run the factory's own program by "
        "a literal first argument, nor are on the allowed list with a reason:\n  "
        + "\n  ".join(problems)
    )


def test_every_runner_environment_place_is_read_from_its_def() -> None:
    """Each generic runner's environment parameter is derived from its own
    signature; one that skips the environment when it is left out must
    actually take one."""
    for (rel, fname), spec in GENERIC_RUNNERS.items():
        kind, _position, _named = _runner_env(rel, fname)
        if spec.get("default_is_safe") or spec.get("none_is_safe"):
            assert kind != "none", f"{rel}:{fname} takes no environment"


def test_every_module_use_allowance_is_still_needed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each MODULE_USE_ALLOWED entry still waives something: without the
    list, the guard reports that place."""
    listed = dict(MODULE_USE_ALLOWED)
    monkeypatch.setitem(globals(), "MODULE_USE_ALLOWED", {})
    problems = unaccounted_launches(PACKAGE)
    unneeded = [
        f"{rel}:{fname}"
        for rel, fname in listed
        if not any(p.startswith(f"{rel}:") and f" in {fname}: " in p for p in problems)
    ]
    assert not unneeded, f"allowances that waive nothing any more: {unneeded}"


def test_the_allowed_list_names_only_real_places() -> None:
    modules = {m.rel: m for m in _load_modules(PACKAGE)}
    missing = []
    for rel, fname in list(ALLOWED) + list(GENERIC_RUNNERS) + list(MODULE_USE_ALLOWED):
        if rel.startswith("guardkit:"):
            continue
        mod = modules.get(rel)
        names = {
            n.name for n in ast.walk(mod.tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        } if mod else set()
        if fname not in names:
            missing.append(f"{rel}:{fname}")
    assert not missing, f"allowed-list entries that name nothing: {missing}"
