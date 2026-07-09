"""Tests for PERMISSIVE_DOUBLE (WS3-S3 2a) — the signature-binding-fake scan."""

from __future__ import annotations

from pathlib import Path

import guardkitfactory.wiring.dialects.python  # noqa: F401 — register dialect
from guardkitfactory.wiring.permissive_double import analyze_permissive_double


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_patched_first_party_implicit_mock_fires(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/svc.py", "def send_payment(a, b):\n    return 1\n")
    _write(tmp_path, "tests/test_x.py",
           "from unittest.mock import patch\n"
           "def test_it():\n"
           "    with patch('pkg.svc.send_payment'):\n"
           "        pass\n")
    r = analyze_permissive_double(["tests/test_x.py"], tmp_path, "FEATURE")
    assert r["ran"] is True
    assert any(f["target_evidence"] == "patched" and "send_payment" in f["symbol"]
               for f in r["findings"])


def test_stdlib_patch_does_not_fire(tmp_path: Path) -> None:
    # R2a-5: first-party positive resolution — patch('time.sleep') must NOT fire.
    _write(tmp_path, "pkg/svc.py", "def real():\n    return 1\n")
    _write(tmp_path, "tests/test_x.py",
           "from unittest.mock import patch\n"
           "def test_it():\n"
           "    with patch('time.sleep'):\n"
           "        pass\n")
    r = analyze_permissive_double(["tests/test_x.py"], tmp_path, "FEATURE")
    assert r["findings"] == []


def test_wraps_delegation_does_not_fire(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/svc.py", "def real(a):\n    return a\n")
    _write(tmp_path, "tests/test_x.py",
           "from unittest.mock import patch\n"
           "from pkg.svc import real\n"
           "def test_it():\n"
           "    with patch('pkg.svc.real', wraps=real):\n"
           "        pass\n")
    r = analyze_permissive_double(["tests/test_x.py"], tmp_path, "FEATURE")
    assert r["findings"] == []


def test_autospec_does_not_fire(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/svc.py", "def real(a):\n    return a\n")
    _write(tmp_path, "tests/test_x.py",
           "from unittest.mock import patch\n"
           "def test_it():\n"
           "    with patch('pkg.svc.real', autospec=True):\n"
           "        pass\n")
    r = analyze_permissive_double(["tests/test_x.py"], tmp_path, "FEATURE")
    assert r["findings"] == []


def test_poc006_spec_mock_is_info_tier2(tmp_path: Path) -> None:
    # AsyncMock(spec=VoiceService) over a first-party seam via patch.object →
    # permissive but spec= is TIER-2 → info severity, not a tier-1 advisory.
    _write(tmp_path, "pkg/svc.py", "class VoiceService:\n    def real(self):\n        return 1\n")
    _write(tmp_path, "tests/test_router.py",
           "from unittest.mock import AsyncMock, patch\n"
           "from pkg.svc import VoiceService\n"
           "def test_router():\n"
           "    with patch.object(VoiceService, 'real', AsyncMock(spec=VoiceService)):\n"
           "        pass\n")
    r = analyze_permissive_double(["tests/test_router.py"], tmp_path, "FEATURE")
    specs = [f for f in r["findings"] if f["form"] == "spec_mock"]
    assert all(f["severity"] == "info" for f in specs)


def test_name_matched_star_args_fake_fires(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/svc.py", "class PaymentGateway:\n    def charge(self, amt):\n        return 1\n")  # noqa: E501
    _write(tmp_path, "tests/test_pay.py",
           "class FakePaymentGateway:\n"
           "    def charge(self, *args, **kwargs):\n"
           "        return None\n")
    r = analyze_permissive_double(["tests/test_pay.py"], tmp_path, "FEATURE")
    assert any(f["target_evidence"] == "name_matched" and f["target"] == "PaymentGateway"
               for f in r["findings"])


def test_getattr_fake_fires(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/svc.py", "class Dispatcher:\n    def run(self):\n        return 1\n")
    _write(tmp_path, "tests/test_d.py",
           "class StubDispatcher:\n"
           "    def __getattr__(self, name):\n"
           "        return lambda *a, **k: None\n")
    r = analyze_permissive_double(["tests/test_d.py"], tmp_path, "FEATURE")
    assert any(f["target"] == "Dispatcher" for f in r["findings"])


def test_bind_escape_not_flagged(tmp_path: Path) -> None:
    # The cure's own star-args surface (sig.bind) must not be flagged.
    _write(tmp_path, "pkg/svc.py", "class Dispatcher:\n    def run(self):\n        return 1\n")
    _write(tmp_path, "tests/test_d.py",
           "import inspect\n"
           "class FakeDispatcher:\n"
           "    def __call__(self, *args, **kwargs):\n"
           "        inspect.signature(self._real).bind(*args, **kwargs)\n")
    r = analyze_permissive_double(["tests/test_d.py"], tmp_path, "FEATURE")
    assert r["findings"] == []


def test_explicit_mirror_fake_not_flagged(tmp_path: Path) -> None:
    # A hand-mirrored explicit-param fake pins the contract as-authored (§2.5).
    _write(tmp_path, "pkg/svc.py", "class Gateway:\n    def charge(self, amt):\n        return 1\n")
    _write(tmp_path, "tests/test_g.py",
           "class FakeGateway:\n"
           "    def charge(self, amt):\n"
           "        return None\n")
    r = analyze_permissive_double(["tests/test_g.py"], tmp_path, "FEATURE")
    assert r["findings"] == []  # no splat → not permissive


def test_non_test_file_not_scanned(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/fakes.py",
           "class FakeThing:\n    def do(self, *a, **k):\n        return None\n")
    # authored a non-test file → 2a scope is test files → no target → None.
    assert analyze_permissive_double(["pkg/fakes.py"], tmp_path, "FEATURE") is None


def test_non_feature_task_none(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_x.py", "def test_it():\n    pass\n")
    assert analyze_permissive_double(["tests/test_x.py"], tmp_path, "DOCUMENTATION") is None
