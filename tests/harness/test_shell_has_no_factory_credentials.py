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


def _launch_kind(mod: _Module, node: ast.AST) -> Optional[str]:
    """What launch ``node`` (a call target or a value) names, if any."""
    if isinstance(node, ast.Attribute):
        if node.attr in _ANY_RECEIVER_LAUNCHES:
            return _dotted(node)
        if isinstance(node.value, ast.Name):
            for module in sorted(mod.imports.get(node.value.id, ())):
                if module in _LAUNCHES and node.attr in _LAUNCHES[module]:
                    return f"{module}.{node.attr}"
    if isinstance(node, ast.Name):
        for target in sorted(mod.imports.get(node.id, ())):
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
            for target in targets:
                module, _, last = target.rpartition(".")
                if last in base or target in HELPERS or (module in _LAUNCHES and last in _LAUNCHES[module]):
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
        for target in targets:
            module, _, last = target.rpartition(".")
            # Only the guarded name's own spelling: any other spelling is an
            # alias, which is a violation in itself (_aliased_guarded_imports).
            if (target in _LAUNCHES or target == "asyncio.subprocess") and name == target.split(".")[0]:
                guarded[name] = "module"
            elif name == last and (
                (module in _LAUNCHES and last in _LAUNCHES[module])
                or target in runner_ids
                or target in HELPERS
            ):
                guarded.setdefault(name, "function")
    for node in mod.tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and f"{mod.dotted}.{node.name}" in runner_ids:
            guarded.setdefault(node.name, "function")
    return guarded


def _launch_attribute_names() -> set:
    names = set(_ANY_RECEIVER_LAUNCHES)
    for launches in _LAUNCHES.values():
        names.update(launches)
    return names


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
    launch_attr = chain.attr in _launch_attribute_names()
    while True:
        above = mod.parents.get(id(chain))
        if isinstance(above, ast.Attribute) and above.value is chain:
            chain = above
            launch_attr = launch_attr or chain.attr in _launch_attribute_names()
            continue
        break
    if launch_attr and not (isinstance(above, ast.Call) and above.func is chain):
        if id(chain) in _annotation_nodes_cache(mod):
            return None
        return (
            f"the launch function {_dotted(chain)} is used other than by calling it, "
            f"so its env= cannot be checked"
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
                    and (a.name in _LAUNCHES or a.name == "asyncio.subprocess")
                ]
            elif isinstance(node, ast.ImportFrom):
                # One resolver for every identity: relative levels included.
                bindings = _import_bindings(node, mod.dotted, mod.rel.endswith("__init__.py"))
                for alias, (_bound, target) in zip(node.names, bindings):
                    if not alias.asname or alias.asname == alias.name:
                        continue
                    module, _, last = target.rpartition(".")
                    if (
                        (module in _LAUNCHES and last in _LAUNCHES[module])
                        or (module.split(".")[0] == "asyncio" and last in _ANY_RECEIVER_LAUNCHES)
                        or (module == "asyncio" and last == "subprocess")
                        or target in runner_ids
                        or target in HELPERS
                        # Belt and braces: a distinctive guarded name is never
                        # aliased, whatever module text it comes from.
                        or alias.name in distinctive
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
        annotations = _annotation_nodes(mod.tree)
        guarded = _guarded_names(mod, runner_ids)
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


def _probe_package(tmp_path: Path, name: str) -> Path:
    pkg = tmp_path / name
    (pkg / "orchestrator").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "orchestrator" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "orchestrator" / "zz_probe.py").write_text(GUARD_PROBES, encoding="utf-8")
    (pkg / "orchestrator" / "zz_rebound.py").write_text(GUARD_PROBES_REBOUND, encoding="utf-8")
    for filename, text in GUARD_PROBES_WILDCARD.items():
        (pkg / "orchestrator" / filename).write_text(text, encoding="utf-8")
    return pkg


def test_the_guard_catches_every_probe(tmp_path: Path) -> None:
    """Synthetic source fed to the guard (never added to the package)."""
    problems = unaccounted_launches(_probe_package(tmp_path, PACKAGE.name))
    named = {p.split(" in ", 1)[1].split(":", 1)[0] for p in problems}
    expected = {
        n.name for n in ast.walk(ast.parse(GUARD_PROBES + "\n" + GUARD_PROBES_REBOUND))
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
