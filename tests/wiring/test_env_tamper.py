"""Tests for SYS_MODULES_TAMPER (WS3-S3 ENVTAMPER-b).

The must-fire fixture reconstructs the ABL-001 run-2 shape (verified 2026-07-09):
a ``sys.modules["nats_core"] = stub`` subscript-assign in the product file
``guardkit/__init__.py``.  Must-NOT-fire fixtures cover the RENV-6 legit idioms.
"""

from __future__ import annotations

from pathlib import Path

import guardkitfactory.wiring.dialects.python  # noqa: F401 — register dialect
from guardkitfactory.wiring.env_tamper import analyze_env_tamper


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_abl001_product_stub_fires(tmp_path: Path) -> None:
    _write(tmp_path, "guardkit/__init__.py",
           "import sys, types\n"
           "__all__ = ['__version__']\n"
           "if 'nats_core' not in sys.modules:\n"
           "    sys.modules['nats_core'] = types.ModuleType('nats_core')\n"
           "    sys.modules['nats_core.events'] = types.ModuleType('nats_core.events')\n")
    r = analyze_env_tamper(["guardkit/__init__.py"], tmp_path, "FEATURE")
    assert r["ran"] is True
    keys = {f["module_key"] for f in r["findings"]}
    assert "nats_core" in keys
    assert "nats_core.events" in keys
    assert all(f["kind"] == "SYS_MODULES_TAMPER" for f in r["findings"])


def test_setdefault_and_update_and_del(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/mod.py",
           "import sys\n"
           "sys.modules.setdefault('a', object())\n"
           "sys.modules.update({'b': object()})\n"
           "del sys.modules['c']\n")
    r = analyze_env_tamper(["pkg/mod.py"], tmp_path, "FEATURE")
    forms = {f["form"] for f in r["findings"]}
    assert {"setdefault", "update", "del"} <= forms


def test_aliased_sys_receiver_fires(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/mod.py",
           "import sys as _s\n"
           "_s.modules['evil'] = object()\n")
    r = analyze_env_tamper(["pkg/mod.py"], tmp_path, "FEATURE")
    assert any(f["module_key"] == "evil" for f in r["findings"])


def test_from_import_modules_receiver_fires(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/mod.py",
           "from sys import modules\n"
           "modules['evil'] = object()\n")
    r = analyze_env_tamper(["pkg/mod.py"], tmp_path, "FEATURE")
    assert any(f["module_key"] == "evil" for f in r["findings"])


def test_self_replacement_not_flagged(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/mod.py",
           "import sys\n"
           "sys.modules[__name__] = object()\n")
    r = analyze_env_tamper(["pkg/mod.py"], tmp_path, "FEATURE")
    assert r["findings"] == []


def test_alias_shim_not_flagged(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/mod.py",
           "import sys\n"
           "sys.modules['pkg.compat'] = sys.modules['pkg.new']\n")
    r = analyze_env_tamper(["pkg/mod.py"], tmp_path, "FEATURE")
    assert r["findings"] == []


def test_non_literal_key_not_flagged(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/mod.py",
           "import sys\n"
           "def register(name, m):\n"
           "    sys.modules[name] = m\n")
    r = analyze_env_tamper(["pkg/mod.py"], tmp_path, "FEATURE")
    assert r["findings"] == []


def test_test_tier_files_exempt(tmp_path: Path) -> None:
    _write(tmp_path, "tests/conftest.py",
           "import sys\n"
           "sys.modules['x'] = object()\n")
    # authored a test file only → no non-test target → None (exempt, AC-009).
    assert analyze_env_tamper(["tests/conftest.py"], tmp_path, "FEATURE") is None


def test_non_feature_task_type_none(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/mod.py", "import sys\nsys.modules['x'] = object()\n")
    assert analyze_env_tamper(["pkg/mod.py"], tmp_path, "DOCUMENTATION") is None


def test_unrelated_subscript_assignment_not_flagged(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/mod.py",
           "d = {}\n"
           "d['key'] = 1\n"
           "obj.cache['x'] = 2\n")
    r = analyze_env_tamper(["pkg/mod.py"], tmp_path, "FEATURE")
    assert r["findings"] == []
