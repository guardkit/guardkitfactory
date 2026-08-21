"""CALLSITE_DRIFT source-reading fidelity — the real-world misfires (2026-08-21).

Measured over 1,068 git-tracked non-test source files across guardkit, forge,
specialist-agent, api_test and study-tutor, this check produced 67 warnings of
which only 2 were real defects.  Every one of the 65 false alarms traced to one
of five ways the scan MIS-READS ordinary Python, and not one of the five was
represented in the existing suite.  Each test below is named for the real file
that exposed it, so the fixture stays anchored to a thing that actually happened.

    1. A comment written inside a call's bracket was counted as a value being
       passed.                       (forge src/forge/cli/_serve_gate_activation.py:393)
    2. A "accepts any extra arguments" parameter (``*args`` / ``**kwargs``)
       stopped being recognised as such once it carried a type annotation.
                                     (forge's ``transition``; guardkit's ``_family``)
    3. A call to a third-party library function was checked against an unrelated
       same-named function elsewhere in the repository.
                                     (api_test's SQLAlchemy ``create_async_engine``)
    4. A decorator that changes what a function accepts was ignored.
                                     (guardkit's click command-line entry point)
    5. A parameter literally named ``self`` or ``cls`` was deleted from EVERY
       function, including plain module-level functions where it is an ordinary
       parameter.                    (guardkit ``qa/formats/base.py`` line 243)

A sixth was found by measuring the repair itself, and is covered in section 6
below:

    6. Fixing (3) made the scan resolve an import to the module it names — but
       the module names it published for its OWN files stripped a leading
       ``src/`` unconditionally.  Right for forge and guardkit; wrong for
       api_test, whose own modules import ``from src.core.config import
       settings``.  In api_test the scan resolved 17 cross-module imports before
       the repair and 0 after.        (api_test, the factory's pilot surface)
"""

from __future__ import annotations

from pathlib import Path

import guardkitfactory.wiring.dialects.python  # noqa: F401 — register dialect
from guardkitfactory.wiring.callsite_drift import analyze_callsite_drift


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. A comment inside the call brackets is not an argument
# ---------------------------------------------------------------------------


def test_comment_inside_call_is_not_counted_as_an_argument(tmp_path: Path) -> None:
    """forge src/forge/cli/_serve_gate_activation.py:393.

    The real call passes ten named values and carries one ``# type: ignore``
    comment on its own line.  The scan reported "passes 1 unnamed value, but
    this function accepts none".
    """
    _write(tmp_path, "forge/gate.py",
           "async def gate_check(*, deps, build_id, feature_id, stage_label,\n"
           "                     target_kind, target_identifier, coach_score=None):\n"
           "    return None\n")
    _write(tmp_path, "forge/cli.py",
           "from forge.gate import gate_check\n"
           "async def activate(deps, bid, fid):\n"
           "    return await gate_check(\n"
           "        deps=deps,\n"
           "        build_id=bid,\n"
           "        feature_id=fid,\n"
           "        stage_label='gate',\n"
           "        target_kind='feature',  # type: ignore[arg-type]\n"
           "        # a whole-line comment too\n"
           "        target_identifier=fid,\n"
           "    )\n")
    r = analyze_callsite_drift(["forge/cli.py"], tmp_path, "FEATURE")
    assert r["findings"] == [], r["findings"]


def test_comment_only_call_is_a_zero_argument_call(tmp_path: Path) -> None:
    """A call whose brackets hold nothing but a comment passes zero values."""
    _write(tmp_path, "pkg/api.py", "def build(a):\n    return a\n")
    _write(tmp_path, "pkg/use.py",
           "from pkg.api import build\n"
           "def go():\n"
           "    return build(\n        # nothing yet\n    )\n")
    r = analyze_callsite_drift(["pkg/use.py"], tmp_path, "FEATURE")
    # Zero values passed against one required parameter → still a real finding.
    assert [f["form"] for f in r["findings"]] == ["missing_required"], r["findings"]


# ---------------------------------------------------------------------------
# 2. An annotated catch-all parameter is still a catch-all
# ---------------------------------------------------------------------------


def test_annotated_double_star_kwargs_still_accepts_extra_names(tmp_path: Path) -> None:
    """forge src/forge/lifecycle/state_machine.py ``transition(**fields: Any)``.

    ``**fields`` means "I accept any extra named values".  Written with a type
    annotation the scan stopped seeing the catch-all and read ``fields`` as an
    ordinary named slot, condemning six correct callers.
    """
    _write(tmp_path, "forge/state_machine.py",
           "from typing import Any\n"
           "def transition(record, to_state, **fields: Any):\n"
           "    return record\n")
    _write(tmp_path, "forge/persistence.py",
           "from forge.state_machine import transition as compose_transition\n"
           "def save(rec):\n"
           "    return compose_transition(rec, 'DONE', error=None, pr_url='x', completed_at=1)\n")
    r = analyze_callsite_drift(["forge/persistence.py"], tmp_path, "FEATURE")
    assert r["findings"] == [], r["findings"]


def test_annotated_star_args_still_accepts_extra_positionals(tmp_path: Path) -> None:
    """guardkit ``orchestrator/stamp_normalizer.py`` ``_family(*patterns: str)``.

    All ten of its callers were condemned for "too many unnamed values".
    """
    _write(tmp_path, "gk/stamp_normalizer.py",
           "import re\n"
           "def _family(*patterns: str):\n"
           "    return [re.compile(p) for p in patterns]\n"
           "PATTERNS = _family('a', 'b', 'c', 'd')\n")
    r = analyze_callsite_drift(["gk/stamp_normalizer.py"], tmp_path, "FEATURE")
    assert r["findings"] == [], r["findings"]


def test_annotated_catch_all_does_not_become_a_required_parameter(tmp_path: Path) -> None:
    """The catch-all must not be counted as a parameter that MUST be supplied."""
    _write(tmp_path, "pkg/api.py",
           "from typing import Any\n"
           "def build(a, **rest: Any):\n    return a\n")
    _write(tmp_path, "pkg/use.py",
           "from pkg.api import build\n"
           "def go():\n    return build(a=1)\n")
    r = analyze_callsite_drift(["pkg/use.py"], tmp_path, "FEATURE")
    assert r["findings"] == [], r["findings"]


def test_bare_star_before_keyword_only_params_is_still_a_separator(tmp_path: Path) -> None:
    """Guard: the lone ``*`` marker must not be mistaken for a catch-all."""
    _write(tmp_path, "pkg/api.py", "def build(a, *, config):\n    return a\n")
    _write(tmp_path, "pkg/use.py",
           "from pkg.api import build\n"
           "def go():\n    return build(a=1, config=2, nope=3)\n")
    r = analyze_callsite_drift(["pkg/use.py"], tmp_path, "FEATURE")
    assert any(f["form"] == "unknown_kwarg" for f in r["findings"]), r["findings"]


# ---------------------------------------------------------------------------
# 3. A name imported from somewhere else is not this repo's function
# ---------------------------------------------------------------------------


def test_third_party_import_is_not_checked_against_a_repo_namesake(tmp_path: Path) -> None:
    """api_test alembic/env.py + src/db/session.py, SQLAlchemy's ``create_async_engine``.

    The repository happens to contain its own ``create_async_engine``; the scan
    compared SQLAlchemy's call against it and cried wolf twice.
    """
    _write(tmp_path, "app/helpers.py",
           "def create_async_engine(url):\n    return url\n")
    _write(tmp_path, "app/session.py",
           "from sqlalchemy.ext.asyncio import create_async_engine\n"
           "def make(url):\n"
           "    return create_async_engine(url, echo=False, pool_pre_ping=True)\n")
    r = analyze_callsite_drift(["app/session.py"], tmp_path, "FEATURE")
    assert r["findings"] == [], r["findings"]


def test_first_party_import_still_resolves_and_still_fires(tmp_path: Path) -> None:
    """Guard: silencing third-party imports must not silence first-party ones."""
    _write(tmp_path, "app/helpers.py", "def build(url):\n    return url\n")
    _write(tmp_path, "app/session.py",
           "from app.helpers import build\n"
           "def make(url):\n    return build(url, echo=False)\n")
    r = analyze_callsite_drift(["app/session.py"], tmp_path, "FEATURE")
    assert any(f["form"] == "unknown_kwarg" for f in r["findings"]), r["findings"]


def test_relative_import_still_resolves_and_still_fires(tmp_path: Path) -> None:
    """Guard: ``from .helpers import build`` is unambiguously first-party."""
    _write(tmp_path, "app/__init__.py", "")
    _write(tmp_path, "app/helpers.py", "def build(url):\n    return url\n")
    _write(tmp_path, "app/session.py",
           "from .helpers import build\n"
           "def make(url):\n    return build(url, echo=False)\n")
    r = analyze_callsite_drift(["app/session.py"], tmp_path, "FEATURE")
    assert any(f["form"] == "unknown_kwarg" for f in r["findings"]), r["findings"]


# ---------------------------------------------------------------------------
# 4. A decorator can change what a function accepts
# ---------------------------------------------------------------------------


def test_decorated_command_line_entry_point_is_not_checked(tmp_path: Path) -> None:
    """guardkit ``guardkit/cli/main.py`` — a ``click``-built command-line entry point.

    ``@click.group()`` replaces the function with a command object that is
    called with completely different arguments.  Reading the ``def`` line tells
    you nothing about what the decorated name accepts.
    """
    _write(tmp_path, "gk/main.py",
           "import click\n"
           "@click.group()\n"
           "@click.option('--verbose', is_flag=True)\n"
           "def cli(verbose):\n"
           "    pass\n"
           "def run():\n"
           "    return cli(obj={}, standalone_mode=False)\n")
    r = analyze_callsite_drift(["gk/main.py"], tmp_path, "FEATURE")
    assert r["findings"] == [], r["findings"]


def test_signature_preserving_decorator_still_checked(tmp_path: Path) -> None:
    """Guard: ``@functools.cache`` and friends keep the signature — keep checking."""
    _write(tmp_path, "pkg/api.py",
           "import functools\n"
           "@functools.cache\n"
           "def build(a, b):\n    return a\n")
    _write(tmp_path, "pkg/use.py",
           "from pkg.api import build\n"
           "def go():\n    return build(a=1, b=2, nope=3)\n")
    r = analyze_callsite_drift(["pkg/use.py"], tmp_path, "FEATURE")
    assert any(f["form"] == "unknown_kwarg" for f in r["findings"]), r["findings"]


# ---------------------------------------------------------------------------
# 5. ``self`` / ``cls`` is only special as a method's FIRST parameter
# ---------------------------------------------------------------------------


def test_module_level_function_keeps_a_parameter_named_cls(tmp_path: Path) -> None:
    """guardkit ``guardkit/qa/formats/base.py:243``.

    ``def validate_markdown_file(cls, path)`` is a plain module-level function;
    ``cls`` is an ordinary first parameter.  Deleting it made the scan believe
    the function accepts one value when it accepts two.
    """
    _write(tmp_path, "gk/base.py",
           "def validate_markdown_file(cls, path):\n    return (cls, path)\n")
    _write(tmp_path, "gk/formats.py",
           "from gk.base import validate_markdown_file\n"
           "def check(fmt, p):\n    return validate_markdown_file(fmt, p)\n")
    r = analyze_callsite_drift(["gk/formats.py"], tmp_path, "FEATURE")
    assert r["findings"] == [], r["findings"]


def test_method_self_is_still_dropped_for_a_constructor(tmp_path: Path) -> None:
    """Guard: a constructor's leading ``self`` is never passed by the caller."""
    _write(tmp_path, "pkg/svc.py",
           "class Service:\n"
           "    def __init__(self, db, cache):\n        self.db = db\n")
    _write(tmp_path, "pkg/main.py",
           "from pkg.svc import Service\n"
           "def build(d, c):\n    return Service(d, c)\n")
    r = analyze_callsite_drift(["pkg/main.py"], tmp_path, "FEATURE")
    assert r["findings"] == [], r["findings"]


def test_constructor_with_a_second_parameter_named_cls_keeps_it(tmp_path: Path) -> None:
    """Only the LEADING ``self``/``cls`` is the implicit receiver."""
    _write(tmp_path, "pkg/svc.py",
           "class Service:\n"
           "    def __init__(self, cls, db):\n        self.cls = cls\n")
    _write(tmp_path, "pkg/main.py",
           "from pkg.svc import Service\n"
           "def build(k, d):\n    return Service(k, d)\n")
    r = analyze_callsite_drift(["pkg/main.py"], tmp_path, "FEATURE")
    assert r["findings"] == [], r["findings"]


# ---------------------------------------------------------------------------
# Working out WHICH function a name refers to
# ---------------------------------------------------------------------------


def test_same_name_in_two_modules_binds_against_the_imported_one(tmp_path: Path) -> None:
    """forge ``src/forge/tools/guardkit.py:155``.

    ``from forge.adapters.guardkit.run import run as guardkit_run`` was checked
    against an unrelated ``run(argv)`` in ``scripts/`` — the first ``run`` found
    anywhere in the repository — and reported a crash that cannot happen.
    """
    _write(tmp_path, "scripts/activate.py", "def run(argv):\n    return 0\n")
    _write(tmp_path, "src/app/adapters/runner.py",
           "def run(*, subcommand, args, repo_path):\n    return 1\n")
    _write(tmp_path, "src/app/tools/call.py",
           "from app.adapters.runner import run as app_run\n"
           "def go(p):\n"
           "    return app_run(subcommand='x', args=[], repo_path=p)\n")
    r = analyze_callsite_drift(["src/app/tools/call.py"], tmp_path, "FEATURE")
    assert r["findings"] == [], r["findings"]


def test_wrong_name_against_the_imported_one_still_fires(tmp_path: Path) -> None:
    """Guard: binding the RIGHT function must still catch a wrong argument."""
    _write(tmp_path, "scripts/activate.py", "def run(argv):\n    return 0\n")
    _write(tmp_path, "src/app/adapters/runner.py",
           "def run(*, subcommand, args):\n    return 1\n")
    _write(tmp_path, "src/app/tools/call.py",
           "from app.adapters.runner import run as app_run\n"
           "def go():\n    return app_run(subcommand='x', args=[], nope=1)\n")
    r = analyze_callsite_drift(["src/app/tools/call.py"], tmp_path, "FEATURE")
    assert any(f["form"] == "unknown_kwarg" for f in r["findings"]), r["findings"]


def test_name_published_through_a_package_init_is_followed_home(tmp_path: Path) -> None:
    """guardkit ``guardkit.orchestrator.harness`` publishes ``select_harness``.

    The name is written in the package's private ``selector`` module and handed
    out by the package's ``__init__``.  Refusing to follow that hop would blind
    the scan to every name a package re-exports — most of guardkit's.
    """
    _write(tmp_path, "src/app/harness/__init__.py",
           "from .selector import select_harness\n")
    _write(tmp_path, "src/app/harness/selector.py",
           "def select_harness(env_var='X', *, cwd):\n    return env_var\n")
    _write(tmp_path, "src/app/caller.py",
           "from app.harness import select_harness\n"
           "def go():\n    return select_harness(cwd='.', bogus=1)\n")
    r = analyze_callsite_drift(["src/app/caller.py"], tmp_path, "FEATURE")
    assert any(f["symbol"] == "select_harness" and f["form"] == "unknown_kwarg"
               for f in r["findings"]), r["findings"]


def test_a_correct_call_through_a_package_init_stays_quiet(tmp_path: Path) -> None:
    _write(tmp_path, "src/app/harness/__init__.py",
           "from .selector import select_harness\n")
    _write(tmp_path, "src/app/harness/selector.py",
           "def select_harness(env_var='X', **harness_kwargs):\n    return env_var\n")
    _write(tmp_path, "src/app/caller.py",
           "from app.harness import select_harness\n"
           "def go():\n    return select_harness(cwd='.', timeout=1)\n")
    r = analyze_callsite_drift(["src/app/caller.py"], tmp_path, "FEATURE")
    assert r["findings"] == [], r["findings"]


def test_plain_module_import_never_binds_a_signature(tmp_path: Path) -> None:
    """``import shutil`` binds a module name, not something to check calls against."""
    _write(tmp_path, "pkg/which.py", "def which(a, b, c):\n    return a\n")
    _write(tmp_path, "pkg/use.py",
           "import shutil\n"
           "def go():\n    return shutil(1)\n")
    r = analyze_callsite_drift(["pkg/use.py"], tmp_path, "FEATURE")
    assert r["findings"] == [], r["findings"]


# ---------------------------------------------------------------------------
# THE CASE THAT MATTERS — permanent regression guard
# ---------------------------------------------------------------------------


def test_the_forge_planning_boot_defect_is_still_caught(tmp_path: Path) -> None:
    """forge commit ``1fcb72c``, ``src/forge/cli/serve.py`` lines 446 / 452 / 457.

    This is the defect class the whole check exists for, and it has bitten this
    estate three times.  Three planning functions were renamed to take
    ``db_path`` / ``nats_client`` / ``config``; the boot path in ``serve.py``
    kept passing the old ``sqlite_pool`` / ``client`` / ``planning_config``
    names.  Nothing failed until the daemon actually booted with planning
    enabled, whereupon every one of the three raised TypeError.

    The fixture is a faithful miniature of that commit — same import shape
    (three names taken from one first-party module), same keyword-only
    signature, same three wrong names — so it can never rot the way a vendored
    copy of the repository would.  Replayed against the real commit this scan
    produces exactly these three warnings and nothing else.

    IF A CHANGE TO THIS SCAN MAKES THIS TEST PASS SILENTLY, THE CHANGE IS WRONG.
    """
    _write(tmp_path, "src/forge/cli/_serve_planning.py",
           "async def compose_planning_consumer_and_dispatch(\n"
           "    *, db_path, nats_client, config, clock=None,\n"
           "):\n    return None\n"
           "\n"
           "async def rearm_paused_planning_runs(*, db_path, nats_client, config):\n"
           "    return None\n"
           "\n"
           "async def sweep_interrupted_planning_runs(*, db_path, nats_client, config):\n"
           "    return None\n")
    _write(tmp_path, "src/forge/cli/serve.py",
           "from forge.cli._serve_planning import (\n"
           "    compose_planning_consumer_and_dispatch,\n"
           "    rearm_paused_planning_runs,\n"
           "    sweep_interrupted_planning_runs,\n"
           ")\n"
           "\n"
           "async def _boot(client, sqlite_pool, forge_config):\n"
           "    if forge_config.planning.enabled:\n"
           "        await compose_planning_consumer_and_dispatch(\n"
           "            client=client,\n"
           "            planning_config=forge_config.planning,\n"
           "            sqlite_pool=sqlite_pool,\n"
           "            config=forge_config,\n"
           "        )\n"
           "        await sweep_interrupted_planning_runs(\n"
           "            sqlite_pool=sqlite_pool,\n"
           "            client=client,\n"
           "            planning_config=forge_config.planning,\n"
           "        )\n"
           "        await rearm_paused_planning_runs(\n"
           "            sqlite_pool=sqlite_pool,\n"
           "            client=client,\n"
           "            planning_config=forge_config.planning,\n"
           "        )\n")
    r = analyze_callsite_drift(["src/forge/cli/serve.py"], tmp_path, "FEATURE")
    caught = {f["symbol"] for f in r["findings"] if f["form"] == "unknown_kwarg"}
    assert caught == {
        "compose_planning_consumer_and_dispatch",
        "sweep_interrupted_planning_runs",
        "rearm_paused_planning_runs",
    }, r["findings"]
    # ...and nothing else: the real replay had zero false alarms in this file.
    assert len(r["findings"]) == 3, r["findings"]
    why = next(f["why"] for f in r["findings"]
               if f["symbol"] == "compose_planning_consumer_and_dispatch")
    assert "client" in why and "planning_config" in why and "sqlite_pool" in why


# ---------------------------------------------------------------------------
# 6. A repository whose own code imports through a ``src.`` prefix
# ---------------------------------------------------------------------------
#
# The sixth misfire, found by measuring the repair itself (2026-08-21).  Fixing
# misfire 3 taught the scan to resolve an import to the module it names — but
# the module names it published for its own files were built by stripping a
# leading ``src/`` unconditionally.  That is right for forge and guardkit, and
# wrong for api_test, whose own modules import ``from src.core.config import
# settings``.  In api_test — the factory's pilot surface — NOT ONE cross-module
# import resolved any more: 17 bindings before the repair, 0 after.  A checker
# that says nothing about the one repository the pipeline completes work in is
# worse than the false alarms it replaced.


def test_a_repository_that_imports_through_src_is_still_checked(tmp_path: Path) -> None:
    """api_test: ``from src.users.crud import create_user``.

    The repository root is on the import path and ``src`` is itself a package,
    so ``src/users/crud.py`` IS the module ``src.users.crud``.
    """
    _write(tmp_path, "src/__init__.py", "")
    _write(tmp_path, "src/users/__init__.py", "")
    _write(tmp_path, "src/users/crud.py",
           "def create_user(db, payload):\n    return None\n")
    _write(tmp_path, "src/users/router.py",
           "from src.users.crud import create_user\n"
           "\n"
           "def post_user(db, payload):\n"
           "    return create_user(db, payload, notify=True)\n")
    r = analyze_callsite_drift(["src/users/router.py"], tmp_path, "FEATURE")
    assert [f["symbol"] for f in r["findings"]] == ["create_user"], r["findings"]
    assert r["findings"][0]["form"] == "unknown_kwarg"


def test_the_stripped_reading_of_the_same_layout_still_works(tmp_path: Path) -> None:
    """forge: ``src/forge/...`` is installed as ``forge.…`` and imported that way.

    Both readings of a ``src/`` tree are published, so the same file resolves
    under whichever name the import actually writes.
    """
    _write(tmp_path, "src/forge/store.py", "def save(record):\n    return record\n")
    _write(tmp_path, "src/forge/api.py",
           "from forge.store import save\n"
           "def handle(rec):\n    return save(rec, flush=True)\n")
    r = analyze_callsite_drift(["src/forge/api.py"], tmp_path, "FEATURE")
    assert [f["symbol"] for f in r["findings"]] == ["save"], r["findings"]


def test_relative_import_inside_a_src_prefixed_repository(tmp_path: Path) -> None:
    """``from .crud import create_user`` resolves under either reading."""
    _write(tmp_path, "src/__init__.py", "")
    _write(tmp_path, "src/users/__init__.py", "")
    _write(tmp_path, "src/users/crud.py", "def create_user(db):\n    return None\n")
    _write(tmp_path, "src/users/router.py",
           "from .crud import create_user\n"
           "def post_user(db):\n    return create_user(db, extra=1)\n")
    r = analyze_callsite_drift(["src/users/router.py"], tmp_path, "FEATURE")
    assert [f["symbol"] for f in r["findings"]] == ["create_user"], r["findings"]


def test_a_third_party_import_stays_silent_in_a_src_prefixed_repository(
    tmp_path: Path,
) -> None:
    """The recovered coverage must not undo the bias to silence.

    api_test imports SQLAlchemy's ``create_async_engine`` and also happens to
    define a same-named helper of its own.  Checking the call against the local
    helper is exactly the misfire that was fixed; widening the module names the
    repository publishes must not bring it back.
    """
    _write(tmp_path, "src/__init__.py", "")
    _write(tmp_path, "src/db/__init__.py", "")
    _write(tmp_path, "src/db/helpers.py",
           "def create_async_engine(url):\n    return url\n")
    _write(tmp_path, "src/db/session.py",
           "from sqlalchemy.ext.asyncio import create_async_engine\n"
           "def build(url):\n"
           "    return create_async_engine(url, pool_size=5, echo=False)\n")
    r = analyze_callsite_drift(["src/db/session.py"], tmp_path, "FEATURE")
    assert r["findings"] == [], r["findings"]


def test_two_files_claiming_one_module_name_are_not_guessed_between(
    tmp_path: Path,
) -> None:
    """``src/app.py`` and ``app.py`` both answer to ``app`` — so neither is used.

    Publishing both readings of a ``src/`` tree creates the possibility of two
    files claiming one dotted name.  Nothing in the source says which the import
    meant, so the contested name is dropped and the scan stays silent rather
    than binding against whichever was read first.
    """
    _write(tmp_path, "app.py", "def build(a):\n    return a\n")
    _write(tmp_path, "src/app.py", "def build(a, b, c):\n    return (a, b, c)\n")
    _write(tmp_path, "caller.py",
           "from app import build\n"
           "def go():\n    return build(1, 2, 3, 4)\n")
    r = analyze_callsite_drift(["caller.py"], tmp_path, "FEATURE")
    assert r["findings"] == [], r["findings"]


def test_module_aliases_publishes_both_readings_of_a_src_tree() -> None:
    """The unit behind the fix, stated directly."""
    from guardkitfactory.wiring.callsite_drift import module_aliases
    from guardkitfactory.wiring.dialect import get_dialect

    py = get_dialect("python")
    assert module_aliases("src/forge/cli/serve.py", py) == (
        "src.forge.cli.serve", "forge.cli.serve",
    )
    # A package __init__ names the package, not a module called "__init__".
    assert module_aliases("src/users/__init__.py", py) == ("src.users", "users")
    # No source-root prefix → exactly one reading.
    assert module_aliases("guardkit/cli/main.py", py) == ("guardkit.cli.main",)
