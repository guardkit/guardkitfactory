"""Session setup for the whole test suite.

dcode reads ``DEEPAGENTS_HOME`` once, when it is first imported, and the
Player launches only on that profile (``dcode_harness._validate_launch``). The
GitHub workflow runs ``pytest tests/`` without setting it, so the session gets
a fresh private profile here unless the caller chose one.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile

import pytest

if not os.environ.get("DEEPAGENTS_HOME"):
    _profile = tempfile.mkdtemp(prefix="guardkitfactory-tests-dcode-home-")
    os.environ["DEEPAGENTS_HOME"] = _profile
    atexit.register(shutil.rmtree, _profile, ignore_errors=True)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "real_short_tmp: the test uses the real /tmp for the shells' short TMPDIR",
    )


@pytest.fixture(autouse=True)
def _short_tmpdirs_under_pytest(request, tmp_path_factory):
    """The shells' short TMPDIR folders (and GuardKit's, when its version has
    them) go under pytest's own base folder, which pytest clears, not the real
    /tmp, so a run of the suite leaves no /tmp/gkf-* or /tmp/gk-* folders. A
    test of the real place is marked ``real_short_tmp``.

    A private MonkeyPatch, not the ``monkeypatch`` fixture: an autouse fixture
    that asks for that one makes it the first set up and the last undone, so a
    test's own patches would still be in place while its other fixtures clean
    up."""
    if request.node.get_closest_marker("real_short_tmp"):
        yield
        return
    base = str(tmp_path_factory.getbasetemp())
    from guardkitfactory.harness import backend_config

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(backend_config, "SHORT_TMP_ROOT", base)
        try:
            from guardkit.orchestrator import project_command_env
        except ImportError:
            project_command_env = None
        if project_command_env is not None and hasattr(
            project_command_env, "SHORT_TMP_ROOT"
        ):
            patch.setattr(project_command_env, "SHORT_TMP_ROOT", base)
        yield
