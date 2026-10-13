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
from typing import Any, Dict, Iterable, List, Optional, Tuple

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


def _which(name: str) -> Optional[str]:
    import shutil

    return shutil.which(name)


# ---------------------------------------------------------------------------
# Section 5: every process launch in the package is accounted for
# ---------------------------------------------------------------------------

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "guardkitfactory"

#: Launches that are allowed as they are, with a one-line reason each.
ALLOWED: Dict[Tuple[str, str], str] = {
    ("code_search.py", "toolkit"): (
        "the factory's own pinned search programs' --version, with a fixed "
        "six-name environment (_git_environment)"
    ),
    ("code_search.py", "_execute"): (
        "the factory's own pinned search programs and git, with a fixed "
        "six-name environment (_git_environment)"
    ),
}

#: No generic runners in this package.
GENERIC_RUNNERS: Dict[Tuple[str, str], Dict[str, Any]] = {}

#: The repository's helper. A launch whose ``env=`` is one of these calls (or
#: a function that only ever returns one) is a project command done right.
HELPERS = {"project_command_environment", "finish_project_environment"}

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

def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    return "?"


def _callee_name(call: ast.Call) -> str:
    return _dotted(call.func)


def _short_name(call: ast.Call) -> str:
    f = call.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return ""


class _Module(SimpleNamespace):
    rel: str
    tree: ast.Module
    parents: Dict[int, ast.AST]


def _load_modules(package: Path) -> List[_Module]:
    modules = []
    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents: Dict[int, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[id(child)] = node
        modules.append(_Module(rel=str(path.relative_to(package)), tree=tree, parents=parents))
    return modules


def _enclosing_function(mod: _Module, node: ast.AST) -> Optional[ast.AST]:
    current = mod.parents.get(id(node))
    while current is not None and not isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
        current = mod.parents.get(id(current))
    return current


def _launch_aliases(tree: ast.Module) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Module aliases (``import subprocess as sp``) and direct names
    (``from subprocess import run``) for the launch modules."""
    modules: Dict[str, str] = {}
    direct: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _LAUNCHES:
                    modules[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module in _LAUNCHES:
            for alias in node.names:
                if alias.name in _LAUNCHES[node.module]:
                    direct[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return modules, direct


def _is_launch(call: ast.Call, modules: Dict[str, str], direct: Dict[str, str]) -> bool:
    f = call.func
    if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
        module = modules.get(f.value.id)
        return module is not None and f.attr in _LAUNCHES[module]
    if isinstance(f, ast.Name):
        return f.id in direct
    return False


def _module_constants(modules: Iterable[_Module]) -> Dict[str, ast.AST]:
    out: Dict[str, ast.AST] = {}
    for mod in modules:
        for node in mod.tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        out[target.id] = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value:
                out[node.target.id] = node.value
    return out


def _factory_literal(
    node: Optional[ast.AST], constants: Dict[str, ast.AST], func: Optional[ast.AST] = None
) -> bool:
    """A list whose first item is the literal git/docker/pgrep/ps."""
    if node is None:
        return False
    if isinstance(node, ast.Name) and func is not None:
        values = _assignments(func, node.id)
        if values and all(_factory_literal(v, constants) for v in values):
            return True
    if isinstance(node, (ast.List, ast.Tuple)):
        return bool(node.elts) and isinstance(node.elts[0], ast.Constant) and node.elts[0].value in FACTORY_PROGRAMS
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _factory_literal(node.left, constants)
    if isinstance(node, ast.Call) and _dotted(node.func) in ("list", "tuple") and node.args:
        return _factory_literal(node.args[0], constants)
    if isinstance(node, ast.Name) and node.id in constants:
        return _factory_literal(constants[node.id], constants)
    return False


def _assignments(func: ast.AST, name: str) -> List[ast.AST]:
    values: List[ast.AST] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                values.append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            if node.value is not None:
                values.append(node.value)
    return values


def _helper_shaped(
    node: Optional[ast.AST], func: Optional[ast.AST], wrappers: set, none_is_safe: bool = False
) -> bool:
    """True when ``node`` (an ``env=`` value) can only be the helper's result."""
    if node is None:
        return False
    if isinstance(node, ast.Call):
        return _short_name(node) in HELPERS or _short_name(node) in wrappers
    if isinstance(node, ast.IfExp):
        return _helper_shaped(node.body, func, wrappers, none_is_safe) and _helper_shaped(
            node.orelse, func, wrappers, none_is_safe
        )
    if isinstance(node, ast.Constant) and node.value is None:
        return none_is_safe
    if isinstance(node, ast.Dict) and not node.keys:
        return True  # an empty environment holds nothing
    if isinstance(node, ast.Name) and func is not None:
        values = _assignments(func, node.id)
        return bool(values) and all(_helper_shaped(v, None, wrappers, none_is_safe) for v in values)
    return False


def _wrappers(modules: List[_Module]) -> set:
    """Functions whose every return is the helper's result (found, not listed)."""
    found: set = set()
    changed = True
    while changed:
        changed = False
        for mod in modules:
            for node in ast.walk(mod.tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name in found:
                    continue
                returns = [
                    r for r in ast.walk(node)
                    if isinstance(r, ast.Return) and _enclosing_function(mod, r) is node
                ]
                if returns and all(_helper_shaped(r.value, node, found) for r in returns):
                    found.add(node.name)
                    changed = True
    return found


def _env_keyword(call: ast.Call) -> Optional[ast.AST]:
    for kw in call.keywords:
        if kw.arg == "env":
            return kw.value
    return None


def _first_argument(call: ast.Call) -> Optional[ast.AST]:
    if call.args:
        return call.args[0]
    for kw in call.keywords:
        if kw.arg in ("args", "argv", "command", "cmd"):
            return kw.value
    return None


def _runner_call_matches(call: ast.Call, names: set) -> bool:
    dotted = _callee_name(call)
    for name in names:
        if name.startswith("*"):
            if dotted.endswith(name[1:]) and dotted != name[1:].lstrip("."):
                return True
        elif dotted == name:
            return True
    return False


def unaccounted_launches(package: Path) -> List[str]:
    modules = _load_modules(package)
    constants = _module_constants(modules)
    wrappers = _wrappers(modules)
    problems: List[str] = []

    def judge(mod: _Module, call: ast.Call, what: str, *, default_is_helper=False, none_is_safe=False) -> None:
        func = _enclosing_function(mod, call)
        fname = getattr(func, "name", "<module>")
        if (mod.rel, fname) in ALLOWED:
            return
        if _factory_literal(_first_argument(call), constants, func):
            return
        env = _env_keyword(call)
        if env is None and default_is_helper:
            return
        if _helper_shaped(env, func, wrappers, none_is_safe):
            return
        reason = "no env= (it inherits everything)" if env is None else "env= is not the helper's"
        problems.append(f"{mod.rel}:{call.lineno} in {fname}: {what}: {reason}")

    for mod in modules:
        aliases, direct = _launch_aliases(mod.tree)
        for node in ast.walk(mod.tree):
            if isinstance(node, ast.Call) and _is_launch(node, aliases, direct):
                judge(mod, node, f"process launch {_callee_name(node)}")
    for (rel, fname), spec in GENERIC_RUNNERS.items():
        for mod in modules:
            if spec.get("scope") and mod.rel not in spec["scope"]:
                continue
            for node in ast.walk(mod.tree):
                if not isinstance(node, ast.Call) or not _runner_call_matches(node, spec["names"]):
                    continue
                func = _enclosing_function(mod, node)
                if mod.rel == rel and getattr(func, "name", None) == fname:
                    continue  # the runner's own body
                judge(
                    mod, node, f"call to the generic runner {fname}",
                    default_is_helper=spec.get("default_is_helper", False),
                    none_is_safe=spec.get("none_is_safe", False),
                )
    return problems


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
        mod = modules.get(rel)
        names = {
            n.name for n in ast.walk(mod.tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        } if mod else set()
        if fname not in names:
            missing.append(f"{rel}:{fname}")
    assert not missing, f"allowed-list entries that name nothing: {missing}"
