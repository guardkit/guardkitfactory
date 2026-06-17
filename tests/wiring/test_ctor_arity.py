"""CTOR_ARITY + spec-mock seam tests (guardkit TASK-AB-WIREGATE01).

The composition-root constructor-arity probe and the extended MOCKED_SEAM
spec-mock detection reproduce the FEAT-POC-006 green≠correct defect: a feature
passes every per-task Coach + the unit suite yet is non-functional because an
integration test ``AsyncMock(spec=Service)``-mocks the primary in-repo seam and
``main.py`` constructs the service with the wrong/missing ``__init__`` args.

AC#6 regression fixtures (FEAT-POC-006 shape):
- (a) integration test ``AsyncMock(spec=VoiceService)`` of a first-party seam → flagged
- (b) composition root missing a required ctor arg → flagged
- (c) a legitimate boundary mock (``patch("httpx.AsyncClient")``) → NOT flagged

AC#4: stack-agnostic — the probe is tree-sitter + DATA (dialect query strings).
AC#5: absence-of-failure-safe — no composition root / unsupported stack /
splat-at-call-or-signature is an *absent* signal, never a pass, never a finding.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from guardkitfactory.wiring import analyze_wiring

# A first-party service whose __init__ takes two required args.
SERVICE_TWO_REQUIRED = (
    "class VoiceService:\n"
    "    def __init__(self, transport, config):\n"
    "        self.transport = transport\n"
    "        self.config = config\n"
)


def _write(worktree: Path, rel: str, content: str) -> str:
    path = worktree / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return rel


def _ctor_findings(result: dict) -> list[dict]:
    return result["ctor_arity"]["findings"]


def _seam_findings(result: dict) -> list[dict]:
    return result["mocked_seam"]["findings"]


# ---------------------------------------------------------------------------
# AC#3 / AC#6(b): composition-root constructor-arity
# ---------------------------------------------------------------------------


class TestCtorArityMissingArg:
    def test_main_constructs_service_missing_required_arg_is_flagged(
        self, tmp_path: Path
    ) -> None:
        """FEAT-POC-006 (b): main.py constructs VoiceService(transport) but
        __init__ requires (transport, config) → CTOR_ARITY finding."""
        svc = _write(tmp_path, "src/voice/service.py", SERVICE_TWO_REQUIRED)
        main = _write(
            tmp_path,
            "main.py",
            "from src.voice.service import VoiceService\n"
            "def build():\n"
            "    return VoiceService(transport)\n",
        )
        result = analyze_wiring([svc, main], tmp_path, "feature")
        findings = _ctor_findings(result)
        assert len(findings) == 1
        f = findings[0]
        assert f["symbol"] == "VoiceService"
        assert f["kind"] == "CTOR_ARITY"
        assert f["pattern"] == "CTOR_ARITY"
        assert f["severity"] == "warning"
        assert f["file"] == "main.py"
        assert result["ctor_arity"]["status"] == "ran"
        assert result["ctor_arity"]["ran"] is True

    def test_extra_positional_args_flagged(self, tmp_path: Path) -> None:
        svc = _write(tmp_path, "src/svc.py", SERVICE_TWO_REQUIRED)
        main = _write(
            tmp_path,
            "main.py",
            "from src.svc import VoiceService\n"
            "def b():\n"
            "    return VoiceService(a, b, c, d)\n",
        )
        result = analyze_wiring([svc, main], tmp_path, "feature")
        findings = _ctor_findings(result)
        assert len(findings) == 1
        assert "at most" in findings[0]["why"]


class TestCtorArityNoFalsePositives:
    @pytest.mark.parametrize(
        "call",
        [
            "VoiceService(t, c)",          # correct positional
            "VoiceService(transport=t, config=c)",  # correct keyword
            "VoiceService(*args)",         # splat at call site → bias OK
            "VoiceService(**kwargs)",      # dict splat at call → bias OK
            "VoiceService(t, **extra)",    # partial splat → bias OK
        ],
    )
    def test_well_formed_or_unknowable_calls_not_flagged(
        self, tmp_path: Path, call: str
    ) -> None:
        svc = _write(tmp_path, "src/svc.py", SERVICE_TWO_REQUIRED)
        main = _write(
            tmp_path,
            "main.py",
            f"from src.svc import VoiceService\ndef b():\n    return {call}\n",
        )
        result = analyze_wiring([svc, main], tmp_path, "feature")
        assert _ctor_findings(result) == []

    def test_variadic_signature_never_flagged(self, tmp_path: Path) -> None:
        """*args/**kwargs in __init__ → arity unknowable → bias OK."""
        svc = _write(
            tmp_path,
            "src/svc.py",
            "class VoiceService:\n    def __init__(self, *args, **kw):\n        pass\n",
        )
        main = _write(
            tmp_path,
            "main.py",
            "from src.svc import VoiceService\ndef b():\n    return VoiceService(t)\n",
        )
        assert _ctor_findings(analyze_wiring([svc, main], tmp_path, "feature")) == []

    def test_defaulted_param_satisfied_not_flagged(self, tmp_path: Path) -> None:
        svc = _write(
            tmp_path,
            "src/svc.py",
            "class VoiceService:\n"
            "    def __init__(self, transport, config=None):\n"
            "        self.t = transport\n",
        )
        main = _write(
            tmp_path,
            "main.py",
            "from src.svc import VoiceService\ndef b():\n    return VoiceService(t)\n",
        )
        assert _ctor_findings(analyze_wiring([svc, main], tmp_path, "feature")) == []

    def test_construction_outside_composition_root_not_scanned(
        self, tmp_path: Path
    ) -> None:
        """A wrong-arity call in a non-composition-root module is not flagged —
        the probe only scans composition roots (main/app/factory/container)."""
        svc = _write(tmp_path, "src/svc.py", SERVICE_TWO_REQUIRED)
        other = _write(
            tmp_path,
            "src/other.py",
            "from src.svc import VoiceService\ndef b():\n    return VoiceService(t)\n",
        )
        result = analyze_wiring([svc, other], tmp_path, "feature")
        assert _ctor_findings(result) == []
        # No composition root scanned → absent signal, never a pass.
        assert result["ctor_arity"]["ran"] is False
        assert result["ctor_arity"]["status"] == "skipped_no_composition_root"

    def test_non_first_party_class_not_flagged(self, tmp_path: Path) -> None:
        """A ctor call to a class with no authored signature is skipped."""
        main = _write(
            tmp_path,
            "main.py",
            "from somewhere import ExternalThing\n"
            "def b():\n    return ExternalThing(a)\n",
        )
        # Author only main.py — ExternalThing has no authored signature.
        result = analyze_wiring([main], tmp_path, "feature")
        assert _ctor_findings(result) == []


class TestCtorArityAbsenceOfFailureSafe:
    def test_unsupported_stack_has_ctor_arity_absent(self, tmp_path: Path) -> None:
        """An unsupported stack yields a ctor_arity block that is absent, not a pass."""
        from types import SimpleNamespace

        _write(tmp_path, "main.go", "package main\n")
        result = analyze_wiring(
            ["main.go"], tmp_path, "feature", stack=SimpleNamespace(language="go")
        )
        assert result["status"] == "unsupported_stack"
        assert "ctor_arity" in result
        assert result["ctor_arity"]["ran"] is False
        assert result["ctor_arity"]["status"] == "unsupported_stack"

    def test_ctor_arity_key_always_present_on_complete(self, tmp_path: Path) -> None:
        svc = _write(tmp_path, "src/svc.py", SERVICE_TWO_REQUIRED)
        result = analyze_wiring([svc], tmp_path, "feature")
        assert "ctor_arity" in result
        # No composition root authored → absent, never a pass.
        assert result["ctor_arity"]["ran"] is False


# ---------------------------------------------------------------------------
# AC#2 / AC#6(a,c): spec-mock seam detection
# ---------------------------------------------------------------------------


class TestSpecMockSeam:
    def test_async_mock_spec_of_first_party_seam_flagged(
        self, tmp_path: Path
    ) -> None:
        """FEAT-POC-006 (a): AsyncMock(spec=VoiceService) of an authored seam."""
        svc = _write(tmp_path, "src/voice/service.py", SERVICE_TWO_REQUIRED)
        test = _write(
            tmp_path,
            "tests/integration/test_router.py",
            "from unittest.mock import AsyncMock\n"
            "def test_router():\n"
            "    svc = AsyncMock(spec=VoiceService)\n"
            "    assert svc is not None\n",
        )
        result = analyze_wiring([svc, test], tmp_path, "feature")
        seams = [f for f in _seam_findings(result) if f["authored_this_turn"]]
        assert any(f["symbol"] == "VoiceService" for f in seams)

    @pytest.mark.parametrize(
        "ctor_expr",
        [
            "MagicMock(spec=VoiceService)",
            "Mock(spec_set=VoiceService)",
            "create_autospec(VoiceService)",
        ],
    )
    def test_other_spec_mock_constructors_flagged(
        self, tmp_path: Path, ctor_expr: str
    ) -> None:
        svc = _write(tmp_path, "src/voice/service.py", SERVICE_TWO_REQUIRED)
        test = _write(
            tmp_path,
            "tests/integration/test_router.py",
            "from unittest.mock import Mock, MagicMock, create_autospec\n"
            "def test_router():\n"
            f"    svc = {ctor_expr}\n"
            "    assert svc is not None\n",
        )
        result = analyze_wiring([svc, test], tmp_path, "feature")
        seams = [f for f in _seam_findings(result) if f["authored_this_turn"]]
        assert any(f["symbol"] == "VoiceService" for f in seams), (
            f"{ctor_expr} should flag the authored seam"
        )

    def test_boundary_mock_not_flagged(self, tmp_path: Path) -> None:
        """FEAT-POC-006 (c): patch('httpx.AsyncClient') is a boundary mock."""
        svc = _write(tmp_path, "src/voice/service.py", SERVICE_TWO_REQUIRED)
        test = _write(
            tmp_path,
            "tests/integration/test_router.py",
            "from unittest.mock import patch\n"
            "def test_router():\n"
            "    with patch('httpx.AsyncClient'):\n"
            "        pass\n",
        )
        result = analyze_wiring([svc, test], tmp_path, "feature")
        authored_seams = [
            f for f in _seam_findings(result) if f["authored_this_turn"]
        ]
        assert authored_seams == []
        ignored = [f["symbol"] for f in result["mocked_seam"]["external_mocks_ignored"]]
        assert "httpx.AsyncClient" in ignored
