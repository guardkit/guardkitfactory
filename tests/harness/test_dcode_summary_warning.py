"""The reworded dcode "summary dropped" warning (19 October 2026).

deepagents-code 0.1.69 warns "Discarding malformed `_summarization_event` ...
re-sends the full history" on every request after a summary, although the model
did receive the summary (test_dcode_summary_window.py). The Player launch
installs a logging filter that rewords that one record, lowers it to INFO and
keeps at most one line a minute. No network, no model, no dcode graph.
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


def _filtered(target: logging.Logger, clock: _Clock | None = None) -> _SummaryFalseAlarm:
    added = _SummaryFalseAlarm("0.1.69", clock or _Clock())
    target.addFilter(added)
    return added


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


@pytest.mark.skipif(
    importlib.util.find_spec("deepagents_code") is None,
    reason="needs the installed deepagents-code to emit its own record",
)
def test_rewords_the_record_the_installed_dcode_emits(notice) -> None:
    from deepagents_code.goal_state_notice import log_malformed_summarization_event

    target, collect = notice
    _filtered(target)
    log_malformed_summarization_event({"cutoff_index": 316}, 9)
    (record,) = collect.records
    assert record.levelno == logging.INFO
    assert "(cutoff_index=316, messages=9)" in record.getMessage()
    assert "re-sends the full history" not in record.getMessage()


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
    messages = [r.getMessage() for r in collect.records]
    assert len(messages) == 3
    assert "(cutoff_index=316, messages=9)" in messages[0]
    assert messages[0].endswith("0 more since the last line.")
    assert messages[1] == "Some other goal-state warning"
    assert "(cutoff_index=316, messages=17)" in messages[2]
    assert messages[2].endswith("3 more since the last line.")


def test_install_is_once_per_process(notice) -> None:
    target, collect = notice
    first = install_summary_warning_filter()
    second = install_summary_warning_filter()
    assert first is second
    assert [f for f in target.filters if isinstance(f, _SummaryFalseAlarm)] == [first]
    # The installed filter names the deepagents-code actually installed.
    target.warning(_UPSTREAM, "316", 9)
    target.warning(_UPSTREAM, "316", 11)
    (record,) = collect.records
    try:
        expected = version("deepagents-code")
    except PackageNotFoundError:
        expected = "(version unknown)"
    assert record.getMessage().startswith(f"Known false alarm from deepagents-code {expected},")
