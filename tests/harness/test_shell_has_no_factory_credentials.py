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
    import importlib

    from guardkitfactory.bdd import plugins
    from guardkitfactory.bdd.loader import ContractTestFailure

    def _fail(name: str) -> Any:
        raise ContractTestFailure(f"{name} failed its checks")

    monkeypatch.setattr(importlib, "import_module", _fail)
    with caplog.at_level(logging.ERROR):
        assert plugins._load("pytest_bdd_plugin", "PytestBDDPlugin") is None
    assert "is not registered" in caplog.text


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

_LAUNCHES = {
    "subprocess": {"run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput"},
    "asyncio": {"create_subprocess_exec", "create_subprocess_shell"},
    "os": {
        "system", "popen", "execl", "execle", "execlp", "execlpe", "execv", "execve",
        "execvp", "execvpe", "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv",
        "spawnve", "spawnvp", "spawnvpe", "posix_spawn", "posix_spawnp", "fork", "forkpty",
    },
    "pty": {"spawn", "fork"},
}
#: Launch methods recognised on any object: ``asyncio.subprocess.create_*``
#: and an event loop's ``subprocess_exec`` / ``subprocess_shell``.
_ANY_RECEIVER_LAUNCHES = {
    "create_subprocess_exec", "create_subprocess_shell", "subprocess_exec", "subprocess_shell",
}
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
    return modules


def _imports(tree: ast.Module, dotted: str, is_package: bool) -> Dict[str, str]:
    """Every name an import binds anywhere in the module -> what it names."""
    out: Dict[str, str] = {}
    package = dotted if is_package else dotted.rsplit(".", 1)[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    out[alias.asname] = alias.name
                else:
                    out[alias.name.split(".")[0]] = alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                anchor = package.split(".")
                anchor = anchor[: len(anchor) - (node.level - 1)]
                base = ".".join([*anchor, base] if base else anchor)
            for alias in node.names:
                out[alias.asname or alias.name] = f"{base}.{alias.name}"
    return out


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
    """The dotted name a call target refers to, or ``None`` when unknown."""
    if isinstance(func_node, ast.Name):
        name = func_node.id
        scope = _enclosing_function(mod, at)
        while scope is not None:  # a function defined in an enclosing function
            for child in ast.iter_child_nodes(scope):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == name:
                    return f"{mod.dotted}.{_qualname(mod, child)}"
            scope = _enclosing_function(mod, scope)
        for child in mod.tree.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child.name == name:
                return f"{mod.dotted}.{name}"
        return mod.imports.get(name)
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


def _is_parameter(func: ast.AST, name: str) -> bool:
    args = func.args
    every = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    every += [a for a in (args.vararg, args.kwarg) if a is not None]
    return any(a.arg == name for a in every)


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
    if target == _FINISH:
        # It copies its input and adds to it: its input must be the helper's.
        given = node.args[0] if node.args else _env_keyword(node)
        return _inline_helper(given, mod, wrappers)
    return target in HELPERS or target in wrappers


def _single_use_helper_name(
    name: str, mod: _Module, func: ast.AST, wrappers: set, is_launch: Callable[[ast.Call], bool]
) -> bool:
    """``name`` is assigned exactly once in ``func``, by a single-target
    assignment of an inline helper call, and every other use of it is as the
    ``env=`` keyword of a launch or generic-runner call in ``func`` itself."""
    if _is_parameter(func, name):
        return False
    values: List[ast.AST] = []
    for node in ast.walk(func):
        if isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names:
            return False
        if isinstance(node, ast.Assign):
            bound = [n for t in node.targets for n in ast.walk(t) if isinstance(n, ast.Name) and n.id == name]
            if bound:
                if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                    return False  # chained or unpacking assignment
                values.append(node.value)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name:
                if node.value is None:
                    return False
                values.append(node.value)
        elif isinstance(node, (ast.AugAssign, ast.NamedExpr, ast.Delete, ast.For, ast.AsyncFor,
                               ast.With, ast.AsyncWith, ast.comprehension, ast.ExceptHandler)):
            targets = []
            if isinstance(node, (ast.AugAssign, ast.NamedExpr, ast.For, ast.AsyncFor, ast.comprehension)):
                targets = [node.target]
            elif isinstance(node, ast.Delete):
                targets = list(node.targets)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                targets = [i.optional_vars for i in node.items if i.optional_vars is not None]
            elif isinstance(node, ast.ExceptHandler) and node.name == name:
                return False
            if any(isinstance(n, ast.Name) and n.id == name for t in targets for n in ast.walk(t)):
                return False
    if len(values) != 1 or not _inline_helper(values[0], mod, wrappers):
        return False
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


def _wrappers(modules: List[_Module]) -> set:
    """Functions whose every return is an inline helper call, by dotted name."""
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
                returns = [
                    r for r in ast.walk(node)
                    if isinstance(r, ast.Return) and _enclosing_function(mod, r) is node
                ]
                if returns and all(
                    isinstance(r.value, ast.Call) and _inline_helper(r.value, mod, found)
                    for r in returns
                ):
                    found.add(full)
                    changed = True
    return found


def _launch_kind(mod: _Module, node: ast.AST) -> Optional[str]:
    """What launch ``node`` (a call target or a value) names, if any."""
    if isinstance(node, ast.Attribute):
        if node.attr in _ANY_RECEIVER_LAUNCHES:
            return _dotted(node)
        if isinstance(node.value, ast.Name):
            module = mod.imports.get(node.value.id)
            if module in _LAUNCHES and node.attr in _LAUNCHES[module]:
                return f"{module}.{node.attr}"
    if isinstance(node, ast.Name):
        target = mod.imports.get(node.id, "")
        module, _, name = target.rpartition(".")
        if module in _LAUNCHES and name in _LAUNCHES[module]:
            return target
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
        return True
    dotted = _callee_name(call)
    return any(dotted.endswith(suffix) for suffix in spec.get("suffixes", ()))


def _callee_name(call: ast.Call) -> str:
    return _dotted(call.func)


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
        none_is_safe=False, env_position: Optional[int] = None,
    ) -> None:
        func, fname = place(mod, call)
        if (mod.rel, fname) in ALLOWED:
            return
        if _factory_literal(call):
            return
        env = _env_keyword(call, env_position)
        if env is None and default_is_safe:
            return
        if _helper_shaped(env, mod, func, wrappers, none_is_safe, launch_checker(mod)):
            return
        reason = "no env= (it inherits everything)" if env is None else "env= is not the helper's"
        problems.append(f"{mod.rel}:{call.lineno} in {fname}: {what}: {reason}")

    for mod in modules:
        called = {id(n.func) for n in ast.walk(mod.tree) if isinstance(n, ast.Call)}
        called |= _annotation_nodes(mod.tree)
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.Call):
                kind = _launch_kind(mod, node.func)
                if kind:
                    judge(mod, node, f"process launch {kind}")
                elif (
                    _dotted(node.func) in ("__import__", "importlib.import_module", "import_module")
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and str(node.args[0].value).split(".")[0] in _LAUNCHES
                ):
                    _, fname = place(mod, node)
                    if (mod.rel, fname) not in ALLOWED:
                        problems.append(
                            f"{mod.rel}:{node.lineno} in {fname}: the launch module "
                            f"{node.args[0].value} is imported by name, so its "
                            f"launches cannot be checked"
                        )
                elif (
                    _dotted(node.func) == "getattr"
                    and len(node.args) >= 2
                    and _launch_kind(
                        mod,
                        ast.Attribute(value=node.args[0], attr=node.args[1].value, ctx=ast.Load())
                        if isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)
                        else ast.Constant(value=None),
                    )
                ):
                    _, fname = place(mod, node)
                    if (mod.rel, fname) not in ALLOWED:
                        problems.append(
                            f"{mod.rel}:{node.lineno} in {fname}: a launch function "
                            f"looked up with getattr, so its env= cannot be checked"
                        )
            elif isinstance(node, (ast.Attribute, ast.Name)) and id(node) not in called:
                if isinstance(getattr(node, "ctx", None), ast.Load) and not isinstance(
                    mod.parents.get(id(node)), ast.Attribute
                ):
                    target = _resolve(mod, node, node)
                    as_runner = target in runner_ids or (
                        isinstance(node, ast.Attribute) and node.attr in runner_attrs
                    )
                    if as_runner:
                        _, fname = place(mod, node)
                        if (mod.rel, fname) not in ALLOWED:
                            problems.append(
                                f"{mod.rel}:{node.lineno} in {fname}: the generic "
                                f"runner {_dotted(node)} is used as a value (held in "
                                f"a variable, passed on or wrapped), so its env= "
                                f"cannot be checked"
                            )
                        continue
                kind = _launch_kind(mod, node)
                if kind and isinstance(getattr(node, "ctx", None), ast.Load):
                    parent = mod.parents.get(id(node))
                    if isinstance(parent, (ast.Attribute,)):
                        continue  # part of a longer dotted name, judged there
                    _, fname = place(mod, node)
                    if (mod.rel, fname) not in ALLOWED:
                        problems.append(
                            f"{mod.rel}:{node.lineno} in {fname}: the launch function "
                            f"{kind} is used as a value (held in a variable, passed "
                            f"on or wrapped), so its env= cannot be checked"
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
                    env_position=spec.get("env_position"),
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


def _probe_package(tmp_path: Path, name: str) -> Path:
    pkg = tmp_path / name
    (pkg / "orchestrator").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "orchestrator" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "orchestrator" / "zz_probe.py").write_text(GUARD_PROBES, encoding="utf-8")
    return pkg


def test_the_guard_catches_every_probe(tmp_path: Path) -> None:
    """Synthetic source fed to the guard (never added to the package)."""
    problems = unaccounted_launches(_probe_package(tmp_path, PACKAGE.name))
    named = {p.split(" in ", 1)[1].split(":", 1)[0] for p in problems}
    expected = {
        n.name for n in ast.walk(ast.parse(GUARD_PROBES))
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name.startswith("v")
    }
    assert expected - named == set(), f"slipped past the guard: {sorted(expected - named)}"
    assert not {
        "ok_helper", "ok_git", "ok_wrapper", "ok_finish", "ok_runner",
        "ok_git_inline_no_env", "ok_git_inline_with_helper",
        "ok_single_use_named_env", "ok_inline_env",
    } & named, problems


def test_every_process_launch_is_accounted_for() -> None:
    problems = unaccounted_launches(PACKAGE)
    assert not problems, (
        "These process launches neither build their environment with "
        "GuardKit's project_command_env, nor run the factory's own program by "
        "a literal first argument, nor are on the allowed list with a reason:\n  "
        + "\n  ".join(problems)
    )


def test_the_allowed_list_names_only_real_places() -> None:
    modules = {m.rel: m for m in _load_modules(PACKAGE)}
    missing = []
    for rel, fname in list(ALLOWED) + list(GENERIC_RUNNERS):
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
