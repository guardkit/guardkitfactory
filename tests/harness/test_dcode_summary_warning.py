"""The reworded dcode "summary dropped" warning (19 October 2026).

deepagents-code 0.1.69 warns "Discarding malformed `_summarization_event` ...
re-sends the full history" on every request after a summary, although the model
did receive the summary (test_dcode_summary_window.py). The Player launch
installs a logging filter that rewords that one record, lowers it to INFO and
keeps at most one line a minute, but only when it comes from the request path
(`_request_with_goal_notice`); from before_model (`_notice_update`) the same
text means the summary really is dropped, so it stays as upstream wrote it.
No network, no model, no dcode graph.
"""

from __future__ import annotations

import importlib.util
import logging
from collections.abc import Iterator
from importlib.metadata import PackageNotFoundError, version

import pytest

from guardkitfactory.harness.dcode_harness import (
    _SummaryFalseAlarm,
    install_summary_warning_filter,
)

_NAME = "deepagents_code.goal_state_notice"
# Exactly the call in deepagents_code/goal_state_notice.py
# (log_malformed_summarization_event), deepagents-code 0.1.69.
_UPSTREAM = (
    "Discarding malformed `_summarization_event` (cutoff_index=%s, "
    "messages=%d); its summary is dropped, so the next request re-sends "
    "the full history."
)


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class _Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def notice(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[logging.Logger, _Collect]]:
    """The real logger, with no filters and a private handler, restored after."""
    target = logging.getLogger(_NAME)
    monkeypatch.setattr(target, "filters", [])
    monkeypatch.setattr(target, "level", logging.DEBUG)
    collect = _Collect()
    target.addHandler(collect)
    yield target, collect
    target.removeHandler(collect)


def _filtered(
    target: logging.Logger, clock: _Clock | None = None, *, request_path: bool = True
) -> _SummaryFalseAlarm:
    """A filter with a fixed version and clock.

    ``request_path`` stands in for the caller check, so hand-built records can
    exercise the wording and the minute; ``False`` keeps the real frame check.
    """
    if request_path:
        added = _SummaryFalseAlarm("0.1.69", clock or _Clock(), caller=lambda: True)
    else:
        added = _SummaryFalseAlarm("0.1.69", clock or _Clock())
    target.addFilter(added)
    return added


_needs_dcode = pytest.mark.skipif(
    importlib.util.find_spec("deepagents_code") is None,
    reason="needs the installed deepagents-code to emit its own record",
)


def _shrunk(count: int = 9, cutoff: int = 316) -> tuple[list, dict]:
    from langchain_core.messages import AIMessage, HumanMessage

    messages = [HumanMessage(f"m{i}") if i % 2 == 0 else AIMessage(f"a{i}") for i in range(count)]
    event = {"cutoff_index": cutoff, "summary_message": HumanMessage("SUMMARY"), "file_path": None}
    return messages, event


def _request_path(count: int = 9) -> None:
    """The false alarm, through the real upstream request-path method."""
    from deepagents_code.goal_tools import GoalToolsMiddleware
    from langchain.agents.middleware.types import ModelRequest

    messages, event = _shrunk(count)
    request = ModelRequest(
        model=None, messages=messages, state={"messages": messages, "_summarization_event": event}
    )
    GoalToolsMiddleware._request_with_goal_notice(request)


def _before_model(count: int = 9) -> dict:
    """A real dropped summary: before_model reads a saved history that shrank."""
    from deepagents_code.goal_tools import GoalToolsMiddleware

    messages, event = _shrunk(count)
    return GoalToolsMiddleware._notice_update({"messages": messages, "_summarization_event": event})


def test_rewords_the_exact_upstream_record(notice) -> None:
    target, collect = notice
    _filtered(target)
    target.warning(_UPSTREAM, "316", 9)
    (record,) = collect.records
    assert record.levelno == logging.INFO and record.levelname == "INFO"
    assert record.getMessage() == (
        "Known false alarm from deepagents-code 0.1.69, not a dropped summary: its "
        "goal-state check saw an already-shortened request (cutoff_index=316, "
        'messages=9) and logged "Discarding malformed `_summarization_event`". '
        "The model still received the summary and the recent messages; nothing "
        "was re-sent. Shown at most once a minute; 0 more since the last line."
    )


@_needs_dcode
def test_rewords_the_record_the_installed_dcode_request_path_emits(notice) -> None:
    target, collect = notice
    _filtered(target, request_path=False)
    _request_path()
    (record,) = collect.records
    assert record.levelno == logging.INFO
    assert "(cutoff_index=316, messages=9)" in record.getMessage()
    assert "re-sends the full history" not in record.getMessage()


@_needs_dcode
def test_a_real_dropped_summary_from_before_model_stays_loud(notice) -> None:
    target, collect = notice
    clock = _Clock()
    _filtered(target, clock, request_path=False)
    _request_path()  # reworded, starts the minute
    clock.now += 1
    update = _before_model()  # inside that minute
    clock.now += 1
    _request_path(11)  # hidden
    clock.now += 60
    _request_path(13)  # shown, counting only the one hidden request-path line
    assert update is not None and update["_summarization_event"] is None  # really dropped
    levels = [r.levelno for r in collect.records]
    messages = [r.getMessage() for r in collect.records]
    assert levels == [logging.INFO, logging.WARNING, logging.INFO]
    assert messages[1] == _UPSTREAM % ("316", 9)
    assert "(cutoff_index=316, messages=13)" in messages[2]
    assert messages[2].endswith("1 more since the last line.")


def test_the_same_record_from_elsewhere_keeps_its_upstream_words(notice) -> None:
    target, collect = notice
    _filtered(target, request_path=False)
    target.warning(_UPSTREAM, "316", 9)
    target.warning(_UPSTREAM, "316", 9)
    assert [r.levelno for r in collect.records] == [logging.WARNING, logging.WARNING]
    assert all(r.getMessage() == _UPSTREAM % ("316", 9) for r in collect.records)


@pytest.mark.parametrize(
    ("message", "args"),
    [
        ("Some other goal-state warning %s", ("x",)),
        ("Discarding something else (cutoff_index=%s, messages=%d)", ("316", 9)),
        # Genuinely malformed events: not the false-alarm shape, left loud.
        (_UPSTREAM, ("None", 9)),
        (_UPSTREAM, ("'316'", 9)),
        (_UPSTREAM, ("-1", 9)),
        (_UPSTREAM, ("[1, 2]... (truncated)", 9)),
        # A cutoff inside the list is not what this filter explains.
        (_UPSTREAM, ("9", 9)),
    ],
)
def test_leaves_every_other_record_alone(notice, message, args) -> None:
    target, collect = notice
    _filtered(target)
    target.warning(message, *args)
    target.warning(message, *args)
    assert [r.levelno for r in collect.records] == [logging.WARNING, logging.WARNING]
    assert all(r.getMessage() == message % args for r in collect.records)


def test_one_line_a_minute_with_the_count_not_shown(notice) -> None:
    target, collect = notice
    clock = _Clock()
    _filtered(target, clock)
    target.warning(_UPSTREAM, "316", 9)
    for window in (11, 13, 15):
        clock.now += 10
        target.warning(_UPSTREAM, "316", window)
    target.warning("Some other goal-state warning")
    clock.now += 30.0  # 60 seconds after the first shown line
    target.warning(_UPSTREAM, "316", 17)
    for window in (19, 21):
        clock.now += 20
        target.warning(_UPSTREAM, "316", window)
    clock.now += 20.0  # 60 seconds after the second shown line
    target.warning(_UPSTREAM, "316", 23)
    messages = [r.getMessage() for r in collect.records]
    assert len(messages) == 4
    assert "(cutoff_index=316, messages=9)" in messages[0]
    assert messages[0].endswith("0 more since the last line.")
    assert messages[1] == "Some other goal-state warning"
    assert "(cutoff_index=316, messages=17)" in messages[2]
    assert messages[2].endswith("3 more since the last line.")
    # The count starts again after each shown line.
    assert "(cutoff_index=316, messages=23)" in messages[3]
    assert messages[3].endswith("2 more since the last line.")


def test_install_is_once_per_process(notice, monkeypatch: pytest.MonkeyPatch) -> None:
    target, collect = notice
    first = install_summary_warning_filter()
    second = install_summary_warning_filter()
    assert first is second
    assert [f for f in target.filters if isinstance(f, _SummaryFalseAlarm)] == [first]
    monkeypatch.setattr(first, "_caller", lambda: True)  # as if from the request path
    # The installed filter names the deepagents-code actually installed.
    target.warning(_UPSTREAM, "316", 9)
    target.warning(_UPSTREAM, "316", 11)
    (record,) = collect.records
    try:
        expected = version("deepagents-code")
    except PackageNotFoundError:
        expected = "(version unknown)"
    assert record.getMessage().startswith(f"Known false alarm from deepagents-code {expected},")
