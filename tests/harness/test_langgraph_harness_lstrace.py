"""TASK-FIX-LSTRACE01: LangSmith executor-teardown-safe regression.

Reproduces and guards the FEAT-E2CB run-1 crash: a ``task_timeout`` teardown shut
down the asyncio loop's default ``ThreadPoolExecutor`` while LangSmith's async
tracing wrapper was dispatching ``_setup_run`` / ``_on_run_end`` to it, raising
``RuntimeError: cannot schedule new futures after shutdown`` and failing BOTH the
player and coach ``agent.ainvoke``.
"""

import asyncio
import concurrent.futures
import contextvars
import os

import pytest

from guardkitfactory.harness import langgraph_harness as h


def _run_aio_to_thread_with_dead_default_executor() -> str:
    """Call LangSmith's aio_to_thread after killing the loop's default executor."""
    from langsmith._internal import _aiter

    async def main() -> str:
        loop = asyncio.get_running_loop()
        dead = concurrent.futures.ThreadPoolExecutor()
        loop.set_default_executor(dead)
        dead.shutdown(wait=False)  # simulate the task_timeout executor teardown
        return await _aiter.aio_to_thread(contextvars.copy_context(), lambda: "ok")

    return asyncio.run(main())


def test_guard_disables_tracing_by_default(monkeypatch):
    """AC-1: with no opt-out, the guard forces LangSmith tracing off."""
    monkeypatch.delenv("GUARDKIT_KEEP_LANGSMITH", raising=False)
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")  # ambient enable
    h._install_langsmith_executor_guard()
    assert os.environ["LANGCHAIN_TRACING_V2"] == "false"
    assert os.environ["LANGSMITH_TRACING"] == "false"


def test_guard_respects_keep_optout(monkeypatch):
    """The GUARDKIT_KEEP_LANGSMITH escape hatch leaves tracing as configured."""
    monkeypatch.setenv("GUARDKIT_KEEP_LANGSMITH", "1")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    h._install_langsmith_executor_guard()
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"


def test_aio_to_thread_survives_dead_default_executor():
    """AC-2/AC-3 (load-bearing): with the override installed, a torn-down default
    executor cannot raise 'cannot schedule new futures after shutdown'."""
    h._install_langsmith_executor_guard()
    assert _run_aio_to_thread_with_dead_default_executor() == "ok"


def test_default_impl_crashes_without_override():
    """Control: prove the crash is real — without the override the default
    impl DOES raise on a dead executor, so the override is not a no-op."""
    import langsmith

    langsmith.set_runtime_overrides(aio_to_thread=None)  # clear override
    try:
        with pytest.raises(
            RuntimeError, match="cannot schedule new futures after shutdown"
        ):
            _run_aio_to_thread_with_dead_default_executor()
    finally:
        h._install_langsmith_executor_guard()  # restore process-global safety
