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

if not os.environ.get("DEEPAGENTS_HOME"):
    _profile = tempfile.mkdtemp(prefix="guardkitfactory-tests-dcode-home-")
    os.environ["DEEPAGENTS_HOME"] = _profile
    atexit.register(shutil.rmtree, _profile, ignore_errors=True)
