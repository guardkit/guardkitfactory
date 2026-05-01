"""Static lint tests for the production Dockerfile skeleton.

These tests assert the supply-chain hardening properties that the
build-time scenarios in ``forge-production-image.feature`` rely on
(scenarios C2, E1.1, E1.3 and acceptance criterion AC-G).

The tests parse the ``Dockerfile`` at the repo root with regular
expressions rather than invoking ``docker build`` so they can run as
fast unit tests in any CI worker without a Docker daemon. The build
smoke test (``docker build -f Dockerfile -t forge:skel-test .``) and
the runtime non-root assertion (``docker run --rm forge:skel-test
id -u``) are intentionally separate CI integration tests and live
outside this module.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Resolve the repository root deterministically from this test module's
# location: tests/dockerfile/test_digest_pinning.py -> two parents up.
REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE_PATH = REPO_ROOT / "Dockerfile"
DOCKERIGNORE_PATH = REPO_ROOT / ".dockerignore"

# Pattern enforcing ASSUM-010 / ADR-ARCH-032: the base image must be
# python:3.14-slim-bookworm pinned to an immutable sha256 digest. A
# floating tag (no @sha256:...) is the failure mode E1.1 explicitly
# guards against, so the regex anchors on the digest separator.
DIGEST_PIN_PATTERN = re.compile(
    r"^FROM\s+python:3\.14-slim-bookworm@sha256:([0-9a-f]{64})"
    r"(?:\s+AS\s+(\w+))?\s*$",
    re.MULTILINE,
)

# Required exclusions in .dockerignore. These keep build context small,
# avoid leaking host-side state into the image (.git history, .env
# secrets, .guardkit autobuild scratch), and prevent test/doc churn from
# busting the build cache.
REQUIRED_DOCKERIGNORE_ENTRIES = (
    ".git",
    ".venv",
    ".guardkit",
    "tasks/",
    "docs/",
    "tests/",
    "__pycache__",
    "*.pyc",
)


@pytest.fixture(scope="module")
def dockerfile_text() -> str:
    """Return the Dockerfile contents, failing fast if it is missing."""
    if not DOCKERFILE_PATH.is_file():
        pytest.fail(
            f"Dockerfile not found at {DOCKERFILE_PATH}. "
            "TASK-F009-002 requires a Dockerfile at the repo root."
        )
    return DOCKERFILE_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def dockerignore_text() -> str:
    """Return the .dockerignore contents, failing fast if it is missing."""
    if not DOCKERIGNORE_PATH.is_file():
        pytest.fail(
            f".dockerignore not found at {DOCKERIGNORE_PATH}. "
            "TASK-F009-002 requires a .dockerignore at the repo root."
        )
    return DOCKERIGNORE_PATH.read_text(encoding="utf-8")


class TestDockerfileExists:
    """AC-A: The Dockerfile lives at the repo root and is readable."""

    def test_dockerfile_present_at_repo_root(self) -> None:
        assert DOCKERFILE_PATH.is_file(), f"Dockerfile must exist at {DOCKERFILE_PATH}"

    def test_dockerignore_present_at_repo_root(self) -> None:
        assert (
            DOCKERIGNORE_PATH.is_file()
        ), f".dockerignore must exist at {DOCKERIGNORE_PATH}"


class TestDigestPinning:
    """ASSUM-010 / E1.1: every FROM is pinned by sha256 digest."""

    def test_every_from_directive_uses_python_3_14_slim_bookworm(
        self, dockerfile_text: str
    ) -> None:
        # Pull every line that starts with FROM and confirm it targets the
        # mandated base image. Catches accidental drift to e.g. python:3.13.
        from_lines = [
            line.strip()
            for line in dockerfile_text.splitlines()
            if line.lstrip().upper().startswith("FROM ")
        ]
        assert from_lines, "Dockerfile must contain at least one FROM directive"
        for line in from_lines:
            assert "python:3.14-slim-bookworm" in line, (
                f"FROM directive {line!r} must target "
                "python:3.14-slim-bookworm (ADR-ARCH-032)"
            )

    def test_every_from_directive_pins_a_sha256_digest(
        self, dockerfile_text: str
    ) -> None:
        # Forbid floating tags: each FROM must include @sha256:<64 hex>.
        from_lines = [
            line.strip()
            for line in dockerfile_text.splitlines()
            if line.lstrip().upper().startswith("FROM ")
        ]
        floating: list[str] = []
        for line in from_lines:
            if not re.search(r"@sha256:[0-9a-f]{64}\b", line):
                floating.append(line)
        assert not floating, (
            "Every FROM must be pinned by sha256 digest (E1.1). "
            f"Floating tags found: {floating}"
        )

    def test_both_stages_share_the_same_digest(self, dockerfile_text: str) -> None:
        # Pinning two different digests would re-introduce the drift
        # surface that ASSUM-010 closes; T7's update-annotations CI
        # check assumes a single digest to compare against.
        digests = {
            match.group(1) for match in DIGEST_PIN_PATTERN.finditer(dockerfile_text)
        }
        assert (
            len(digests) == 1
        ), f"Both Dockerfile stages must pin the SAME sha256 digest. Found: {digests}"


class TestStageStructure:
    """AC-B: Two named stages — ``builder`` and ``runtime``."""

    def test_builder_stage_declared(self, dockerfile_text: str) -> None:
        assert re.search(
            r"^FROM\s+python:3\.14-slim-bookworm@sha256:[0-9a-f]{64}"
            r"\s+AS\s+builder\s*$",
            dockerfile_text,
            re.MULTILINE | re.IGNORECASE,
        ), "Dockerfile must declare a stage named 'builder'"

    def test_runtime_stage_declared(self, dockerfile_text: str) -> None:
        assert re.search(
            r"^FROM\s+python:3\.14-slim-bookworm@sha256:[0-9a-f]{64}"
            r"\s+AS\s+runtime\s*$",
            dockerfile_text,
            re.MULTILINE | re.IGNORECASE,
        ), "Dockerfile must declare a stage named 'runtime'"


class TestNonRootUser:
    """AC-C / C2 scenario: runtime stage runs as ``forge`` (UID 1000)."""

    def test_runtime_stage_creates_forge_user_with_uid_1000(
        self, dockerfile_text: str
    ) -> None:
        # Accept both ``useradd`` and ``adduser`` styles; both must
        # explicitly carry UID 1000 so the assertion baked into the CI
        # runtime test (`docker run forge:skel-test id -u` -> 1000) holds.
        useradd_form = re.search(
            r"useradd[^\n]*--uid\s+1000[^\n]*\bforge\b",
            dockerfile_text,
        )
        useradd_short = re.search(
            r"useradd[^\n]*-u\s+1000[^\n]*\bforge\b",
            dockerfile_text,
        )
        adduser_form = re.search(
            r"adduser[^\n]*--uid\s+1000[^\n]*\bforge\b",
            dockerfile_text,
        )
        assert (
            useradd_form or useradd_short or adduser_form
        ), "Runtime stage must create a 'forge' user pinned to UID 1000"

    def test_user_directive_switches_to_forge_before_entrypoint(
        self, dockerfile_text: str
    ) -> None:
        # Locate the runtime stage block and verify USER forge precedes
        # the ENTRYPOINT directive so the container PID 1 is unprivileged.
        runtime_match = re.search(
            r"^FROM\s+python:3\.14-slim-bookworm@sha256:[0-9a-f]{64}"
            r"\s+AS\s+runtime\b(?P<body>.*)\Z",
            dockerfile_text,
            re.MULTILINE | re.IGNORECASE | re.DOTALL,
        )
        assert runtime_match, "Could not locate the runtime stage body"
        body = runtime_match.group("body")
        user_match = re.search(r"^USER\s+forge\s*$", body, re.MULTILINE | re.IGNORECASE)
        entrypoint_match = re.search(
            r'^ENTRYPOINT\s+\["forge"\]\s*$',
            body,
            re.MULTILINE | re.IGNORECASE,
        )
        assert user_match, "Runtime stage must contain `USER forge`"
        assert entrypoint_match, 'Runtime stage must declare `ENTRYPOINT ["forge"]`'
        assert user_match.start() < entrypoint_match.start(), (
            "`USER forge` must precede `ENTRYPOINT` so the container "
            "starts unprivileged (C2 scenario, AC-G)"
        )


class TestEntrypointAndCmd:
    """AC-D: exec-form ENTRYPOINT and CMD."""

    def test_entrypoint_is_exec_form_forge(self, dockerfile_text: str) -> None:
        # Exec-form ENTRYPOINT (JSON array) is mandatory: shell-form
        # would route through /bin/sh and break signal forwarding.
        assert re.search(
            r'^ENTRYPOINT\s+\["forge"\]\s*$',
            dockerfile_text,
            re.MULTILINE,
        ), 'Dockerfile must declare ENTRYPOINT ["forge"]'

    def test_cmd_is_exec_form_serve(self, dockerfile_text: str) -> None:
        assert re.search(
            r'^CMD\s+\["serve"\]\s*$',
            dockerfile_text,
            re.MULTILINE,
        ), 'Dockerfile must declare CMD ["serve"]'


class TestNoSecretsOrDebugSurface:
    """AC-E / C1, E1.3: no secrets, no SSH, no remote-debugger surface."""

    @pytest.mark.parametrize(
        "forbidden_token,reason",
        [
            ("ANTHROPIC_API_KEY=", "no real provider API keys may be baked in"),
            ("OPENAI_API_KEY=", "no real provider API keys may be baked in"),
            ("GOOGLE_API_KEY=", "no real provider API keys may be baked in"),
            ("openssh-server", "no SSH server may be installed"),
            ("sshd", "no SSH server may be installed"),
            ("debugpy", "no remote-debugger surface in production image"),
            ("ptvsd", "no remote-debugger surface in production image"),
        ],
    )
    def test_no_forbidden_tokens(
        self,
        dockerfile_text: str,
        forbidden_token: str,
        reason: str,
    ) -> None:
        assert (
            forbidden_token.lower() not in dockerfile_text.lower()
        ), f"Dockerfile must not contain {forbidden_token!r}: {reason}"

    def test_no_env_file_copied_into_image(self, dockerfile_text: str) -> None:
        # ``COPY .env`` (or any explicit reference) would burn secrets
        # into a layer; .dockerignore is a defense-in-depth backstop but
        # the Dockerfile must not request the file in the first place.
        forbidden = re.search(
            r"^\s*(COPY|ADD)\s+[^\n]*\.env\b",
            dockerfile_text,
            re.MULTILINE | re.IGNORECASE,
        )
        assert (
            forbidden is None
        ), "Dockerfile must not COPY or ADD a .env file into the image"


class TestDockerignore:
    """AC-F: .dockerignore excludes build-context noise and host state."""

    @pytest.mark.parametrize("entry", REQUIRED_DOCKERIGNORE_ENTRIES)
    def test_dockerignore_excludes_required_entry(
        self, dockerignore_text: str, entry: str
    ) -> None:
        # Match each entry as its own line (allowing trailing slash
        # normalisation) so a stray substring in a comment doesn't pass.
        candidates = {
            entry,
            entry.rstrip("/"),
            entry.rstrip("/") + "/",
        }
        lines = {line.strip() for line in dockerignore_text.splitlines()}
        assert (
            candidates & lines
        ), f".dockerignore must exclude {entry!r} (found lines: {sorted(lines)})"
