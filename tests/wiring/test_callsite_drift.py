"""Tests for CALLSITE_DRIFT (WS3-S3 2b) — the deterministic drift scan.

Fixtures reconstruct the two verified incident apertures (2026-07-09 shape
verification against forge/study-tutor):

* DD4F = aperture B (a NEW wrong call against an UNCHANGED signature).
* SMP3-06 = aperture A (a changed/reduced signature; a STALE call site keeps
  passing a retired kwarg).  Note SMP3-06 is arity-REDUCING, not the "same-arity
  swap" the S2 doc illustrates — a synthetic same-arity rename fixture proves the
  named ``(name, kind, has_default)`` tuple is load-bearing where a counts-only
  summary would miss it.
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
# Aperture B — DD4F: new wrong call against an unchanged signature
# ---------------------------------------------------------------------------


def test_dd4f_aperture_b_unknown_kwarg_fires(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/_serve_planning.py",
           "async def compose(*, db_path, nats_client, config, clock=None):\n    return None\n")
    _write(tmp_path, "pkg/serve.py",
           "from pkg._serve_planning import compose\n"
           "async def serve(client, pool, cfg):\n"
           "    await compose(client=client, planning_config=cfg.planning, sqlite_pool=pool, config=cfg)\n")  # noqa: E501
    r = analyze_callsite_drift(["pkg/serve.py"], tmp_path, "FEATURE")
    assert r["ran"] is True
    forms = {(f["symbol"], f["form"], f["aperture"]) for f in r["findings"]}
    assert ("compose", "unknown_kwarg", "B") in forms


def test_correct_call_does_not_fire(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/api.py", "def build(db_path, config, clock=None):\n    return 1\n")
    _write(tmp_path, "pkg/serve.py",
           "from pkg.api import build\n"
           "def serve(d, c):\n    return build(db_path=d, config=c)\n")
    r = analyze_callsite_drift(["pkg/serve.py"], tmp_path, "FEATURE")
    assert r["findings"] == []


def test_kwargs_signature_silences_unknown_kwarg(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/api.py", "def build(db_path, **kwargs):\n    return 1\n")
    _write(tmp_path, "pkg/serve.py",
           "from pkg.api import build\n"
           "def serve(d):\n    return build(db_path=d, anything=2, more=3)\n")
    r = analyze_callsite_drift(["pkg/serve.py"], tmp_path, "FEATURE")
    assert r["findings"] == []  # **kwargs accepts unknown names (bias OK)


def test_call_splat_silences(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/api.py", "def build(db_path, config):\n    return 1\n")
    _write(tmp_path, "pkg/serve.py",
           "from pkg.api import build\n"
           "def serve(kw):\n    return build(**kw)\n")
    r = analyze_callsite_drift(["pkg/serve.py"], tmp_path, "FEATURE")
    assert r["findings"] == []  # splat at call site → arity unknowable


def test_missing_required(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/api.py", "def build(db_path, config):\n    return 1\n")
    _write(tmp_path, "pkg/serve.py",
           "from pkg.api import build\n"
           "def serve(d):\n    return build(db_path=d)\n")
    r = analyze_callsite_drift(["pkg/serve.py"], tmp_path, "FEATURE")
    assert any(f["form"] == "missing_required" for f in r["findings"])


def test_excess_positional(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/api.py", "def build(a, b):\n    return 1\n")
    _write(tmp_path, "pkg/serve.py",
           "from pkg.api import build\n"
           "def serve():\n    return build(1, 2, 3)\n")
    r = analyze_callsite_drift(["pkg/serve.py"], tmp_path, "FEATURE")
    assert any(f["form"] == "excess_positional" for f in r["findings"])


def test_unresolved_callee_no_finding(tmp_path: Path) -> None:
    # A bare name that is neither same-file nor imported must not resolve.
    _write(tmp_path, "pkg/serve.py", "def serve():\n    return undefined_helper(x=1)\n")
    r = analyze_callsite_drift(["pkg/serve.py"], tmp_path, "FEATURE")
    assert r["findings"] == []


# ---------------------------------------------------------------------------
# Aperture A — SMP3-06: changed/reduced signature, stale call site
# ---------------------------------------------------------------------------


def test_smp3_06_aperture_a_stale_ctor_site(tmp_path: Path) -> None:
    # Current (reduced) ctor: role_config, session_service, orchestrator_factory, event_bus.
    _write(tmp_path, "st/mcp/adapter.py",
           "class MCPAdapter:\n"
           "    def __init__(self, role_config, session_service=None, orchestrator_factory=None, event_bus=None):\n"  # noqa: E501
           "        self.rc = role_config\n")
    # Stale call site keeps the retired write_helper=/graphiti_client=.
    _write(tmp_path, "st/cli/main.py",
           "from st.mcp.adapter import MCPAdapter\n"
           "def serve(rc, of, wh, eb, wrap):\n"
           "    return MCPAdapter(role_config=rc, orchestrator_factory=of, write_helper=wh, event_bus=eb, graphiti_client=wrap)\n")  # noqa: E501
    baseline = {
        "st/mcp/adapter.py": (
            b"class MCPAdapter:\n"
            b"    def __init__(self, role_config, store=None, orchestrator_factory=None, "
            b"write_helper=None, event_bus=None, graphiti_client=None):\n"
            b"        self.rc = role_config\n"
        ),
    }
    # authored this turn = the signature file; main.py is the stale site.
    r = analyze_callsite_drift(["st/mcp/adapter.py"], tmp_path, "FEATURE", baseline_sources=baseline)  # noqa: E501
    assert "A" in r["apertures_run"]
    finding = [f for f in r["findings"] if f["file"].endswith("main.py")]
    assert finding, r["findings"]
    assert finding[0]["form"] == "unknown_kwarg"
    assert finding[0]["symbol"] == "MCPAdapter"


def test_same_arity_rename_proves_named_tuple(tmp_path: Path) -> None:
    # counts preserved (1 required + 1 defaulted before and after); only a NAME
    # changed. A counts-only summary would miss this; the named tuple catches it.
    _write(tmp_path, "m/mod.py", "def fn(a, paramY=None):\n    return a\n")
    _write(tmp_path, "m/caller.py",
           "from m.mod import fn\n"
           "def stale():\n    return fn(a=1, paramX=2)\n")
    baseline = {"m/mod.py": b"def fn(a, paramX=None):\n    return a\n"}
    r = analyze_callsite_drift(["m/mod.py"], tmp_path, "FEATURE", baseline_sources=baseline)
    assert "A" in r["apertures_run"]
    assert any(f["form"] == "unknown_kwarg" and f["file"].endswith("caller.py")
               for f in r["findings"])


def test_default_value_change_is_not_a_signature_change(tmp_path: Path) -> None:
    # Only a default VALUE changed (10 → 20); the bind tuple is identical, so
    # aperture A must not treat it as a changed signature (no stale-site scan).
    _write(tmp_path, "m/mod.py", "def fn(a, timeout=20):\n    return a\n")
    _write(tmp_path, "m/caller.py",
           "from m.mod import fn\n"
           "def ok():\n    return fn(a=1, timeout=5)\n")
    baseline = {"m/mod.py": b"def fn(a, timeout=10):\n    return a\n"}
    r = analyze_callsite_drift(["m/mod.py"], tmp_path, "FEATURE", baseline_sources=baseline)
    assert r["findings"] == []


# ---------------------------------------------------------------------------
# Absent-signal / gating
# ---------------------------------------------------------------------------


def test_non_feature_task_type_returns_none(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/serve.py", "def serve():\n    return 1\n")
    assert analyze_callsite_drift(["pkg/serve.py"], tmp_path, "DOCUMENTATION") is None


def test_no_source_targets_returns_none(tmp_path: Path) -> None:
    assert analyze_callsite_drift([], tmp_path, "FEATURE") is None


def test_test_files_are_not_call_sites(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/api.py", "def build(a):\n    return 1\n")
    _write(tmp_path, "tests/test_x.py",
           "from pkg.api import build\n"
           "def test_it():\n    build(nope=1)\n")
    # authored a test file only → no non-test source target → None.
    assert analyze_callsite_drift(["tests/test_x.py"], tmp_path, "FEATURE") is None
