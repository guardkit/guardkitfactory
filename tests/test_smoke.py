"""Smoke test for the guardkitfactory source scaffold (TASK-HMIG-000R).

Verifies the falsifier-level invariants from the task spec:

1. ``from guardkitfactory import HarnessAdapter`` succeeds.
2. The ``guardkitfactory.harness`` subpackage imports (skeleton at this stage).
3. The four template-derived ``guardkitfactory.lib`` helpers are present and importable:
   ``factory_guards``, ``json_extractor``, ``retry_context``,
   ``session_logging``.

These tests do not exercise behaviour — that is the job of TASK-HMIG-001B
and beyond. They exist purely to prove that the scaffold installs and that
later harness tasks can import what they expect to import.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# AC-002: top-level package surface
# ---------------------------------------------------------------------------

def test_guardkitfactory_package_imports() -> None:
    import guardkitfactory

    # Assert against a semantic-version shape, not a hardcoded string, so the
    # bump-the-version-in-three-places drift that bit nats-core (0.3.0 string
    # pinned in the test outlived two bumps) is structurally impossible here.
    parts = guardkitfactory.__version__.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts), (
        f"unexpected __version__ shape: {guardkitfactory.__version__!r}"
    )


def test_version_matches_pyproject() -> None:
    """``__version__`` must equal the ``[project].version`` in pyproject.toml.

    Guards the pyproject ``version`` ↔ ``__init__.__version__`` drift class:
    the two are edited by hand in separate files. Reading pyproject directly
    (not installed metadata) keeps the guard truthful in a source checkout
    without an editable reinstall after every bump — the drift that outlived
    two nats-core bumps because the test pinned a stale string instead.
    """
    import pathlib
    import tomllib

    import guardkitfactory

    pyproject = pathlib.Path(__file__).resolve().parent.parent / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text())["project"]["version"]
    assert guardkitfactory.__version__ == declared


def test_harness_adapter_exposed_as_public_api() -> None:
    """AC-002: HarnessAdapter is the stable placeholder symbol."""
    from guardkitfactory import HarnessAdapter

    assert HarnessAdapter is not None
    # Concrete behaviour lands in TASK-HMIG-001B / TASK-HMIG-002R; the
    # placeholder deliberately raises so accidental runtime use surfaces.
    with pytest.raises(NotImplementedError):
        HarnessAdapter()


# ---------------------------------------------------------------------------
# AC-003: harness subpackage skeleton
# ---------------------------------------------------------------------------

def test_harness_subpackage_imports() -> None:
    import guardkitfactory.harness

    assert guardkitfactory.harness is not None


# ---------------------------------------------------------------------------
# AC-004 .. AC-007: vendored guardkitfactory.lib helpers importable
# ---------------------------------------------------------------------------

def test_lib_factory_guards_importable() -> None:
    """AC-004: assert_no_system_messages (TASK-REV-R2A1) + assert_tool_inventory."""
    from guardkitfactory.lib.factory_guards import (
        ToolLeakageError,
        assert_no_system_messages,
        assert_tool_inventory,
    )

    assert callable(assert_no_system_messages)
    assert callable(assert_tool_inventory)
    assert issubclass(ToolLeakageError, Exception)

    # Cheap sanity check on the system-message guard since it has no
    # external dependencies.
    assert_no_system_messages({"messages": [{"role": "user", "content": "hi"}]})
    with pytest.raises(ValueError):
        assert_no_system_messages({"messages": [{"role": "system", "content": "no"}]})


def test_lib_json_extractor_importable() -> None:
    """AC-005: 5-strategy JSON extraction cascade."""
    from guardkitfactory.lib.json_extractor import JsonExtractionError, JsonExtractor

    assert hasattr(JsonExtractor, "extract")
    assert issubclass(JsonExtractionError, Exception)

    # Strategy 1 (direct json.loads) — sanity check.
    parsed = JsonExtractor.extract('{"decision": "accept"}')
    assert parsed == {"decision": "accept"}


def test_lib_retry_context_importable() -> None:
    """AC-006: retry input + context manifest construction."""
    from guardkitfactory.lib.retry_context import build_context_manifest, build_retry_input

    assert callable(build_context_manifest)
    assert callable(build_retry_input)

    payload = build_retry_input("prev output", issues=["nope"])
    assert payload["messages"][0]["role"] == "user"


def test_lib_session_logging_importable() -> None:
    """AC-007: per-run diagnostic JSON + logging bootstrap."""
    from guardkitfactory.lib.session_logging import configure_logging, write_session_log

    assert callable(configure_logging)
    assert callable(write_session_log)


# ---------------------------------------------------------------------------
# guardkitfactory.lib aggregate __init__ also re-exports the four helpers cleanly
# ---------------------------------------------------------------------------

def test_lib_package_reexports() -> None:
    from guardkitfactory import lib

    assert hasattr(lib, "assert_no_system_messages")
    assert hasattr(lib, "JsonExtractor")
    assert hasattr(lib, "build_retry_input")
    assert hasattr(lib, "write_session_log")
