"""Live AC-006 reasoning probe — TASK-FIX-AC006SMOKE-LG.

Capture one ``/v1/responses`` ``AIMessage`` from ``gemma4-coach`` running on
the local DGX llama-swap substrate under ``--reasoning auto``, drive it
through :func:`guardkitfactory.harness.extractors.extract_last_ai_reasoning`,
and replay a Coach-style turn end-to-end through the orchestrator
``coach_output_parser.extract_and_write`` to verify that:

* AC-1: the live AIMessage shape is captured and its reasoning location
  (content-block / ``additional_kwargs["reasoning"]`` / typed
  ``content_blocks``) is recorded.
* AC-2: ``extract_last_ai_reasoning`` returns ``> 0`` chars for that shape.
* AC-3: ``coach_output_parser.extract_and_write`` recovers a fenced JSON
  verdict and COACHSF01 does NOT fire.

Run from the factory repo root:

  PYTHONPATH=/home/richardwoollcott/Projects/appmilla_github/guardkit \\
  .venv/bin/python scripts/ac006_smoke_probe.py

Writes ``docs/state/TASK-FIX-AC006SMOKE-LG/{captured_aimessage,probe_report}.json``.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / "docs" / "state" / "TASK-FIX-AC006SMOKE-LG"
STATE_DIR.mkdir(parents=True, exist_ok=True)

LLAMA_SWAP_BASE_URL = os.environ.get("LLAMA_SWAP_BASE_URL", "http://localhost:9000/v1")
COACH_MODEL_ALIAS = os.environ.get("COACH_MODEL_ALIAS", "gemma4-coach")

COACH_SYSTEM_PROMPT = (
    "You are Coach. Evaluate the Player's turn output and emit a structured "
    "verdict. End your response with a fenced ```json block whose top-level "
    'object contains the keys: task_id, turn, decision ("approve" or '
    '"feedback"), and (if feedback) feedback. Do not write anything after '
    "the closing fence."
)

COACH_USER_PROMPT = (
    "Task: TASK-FIX-IA03 turn 1.\n\n"
    "Player turn summary:\n"
    "- 1 file created, 2 files modified (complexity-3 fix).\n"
    "- All quality gates reported PASSED by the Player (compile + tests + lint).\n"
    "- Independent test re-run by Coach: PASSED.\n\n"
    "Emit the verdict. End with the fenced json block."
)


def _record(event: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()


def _summarize_block(block: Any) -> dict[str, Any]:
    """Compress a content block into a JSON-safe summary (no opaque payloads)."""
    if not isinstance(block, dict):
        return {"raw_type": type(block).__name__, "repr": repr(block)[:200]}
    out: dict[str, Any] = {"type": block.get("type")}
    for key in ("text", "reasoning", "id", "status", "role"):
        if key in block:
            val = block[key]
            if isinstance(val, str):
                out[key] = val if len(val) <= 400 else val[:400] + f"…(+{len(val) - 400} chars)"
            else:
                out[key] = val
    if "summary" in block:
        summary = block["summary"]
        out["summary_len"] = len(summary) if isinstance(summary, list) else None
        out["summary_first"] = summary[0] if isinstance(summary, list) and summary else None
    if "encrypted_content" in block:
        ec = block["encrypted_content"]
        out["encrypted_content_len"] = len(ec) if isinstance(ec, str) else None
    return out


def _summarize_content(content: Any) -> dict[str, Any]:
    if isinstance(content, str):
        return {
            "shape": "str",
            "len": len(content),
            "head": content[:400],
        }
    if isinstance(content, list):
        return {
            "shape": "list",
            "len": len(content),
            "block_types": [
                b.get("type") if isinstance(b, dict) else type(b).__name__ for b in content
            ],
            "blocks": [_summarize_block(b) for b in content],
        }
    return {"shape": type(content).__name__, "repr": repr(content)[:400]}


def _summarize_additional_kwargs(kwargs: Any) -> dict[str, Any]:
    if not isinstance(kwargs, dict):
        return {"shape": type(kwargs).__name__}
    out: dict[str, Any] = {"keys": sorted(kwargs.keys())}
    for key in ("reasoning_content", "reasoning"):
        if key in kwargs:
            val = kwargs[key]
            if isinstance(val, str):
                out[key] = {
                    "shape": "str",
                    "len": len(val),
                    "head": val[:400],
                }
            elif isinstance(val, dict):
                out[key] = {
                    "shape": "dict",
                    "keys": sorted(val.keys()),
                    "summary_len": (
                        len(val.get("summary", []))
                        if isinstance(val.get("summary"), list)
                        else None
                    ),
                    "summary_first": (
                        val["summary"][0]
                        if isinstance(val.get("summary"), list) and val["summary"]
                        else None
                    ),
                    "text_len": (
                        len(val.get("text", "")) if isinstance(val.get("text"), str) else None
                    ),
                    "text_head": (
                        val.get("text", "")[:400] if isinstance(val.get("text"), str) else None
                    ),
                    "encrypted_content_len": (
                        len(val.get("encrypted_content", ""))
                        if isinstance(val.get("encrypted_content"), str)
                        else None
                    ),
                }
            else:
                out[key] = {"shape": type(val).__name__, "repr": repr(val)[:200]}
    return out


def phase_a_capture() -> tuple[Any, dict[str, Any]]:
    """AC-1: capture one live ``/v1/responses`` AIMessage from gemma4-coach."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    _record(
        {
            "phase": "A",
            "step": "build_client",
            "base_url": LLAMA_SWAP_BASE_URL,
            "model": COACH_MODEL_ALIAS,
        }
    )

    chat = ChatOpenAI(
        model=COACH_MODEL_ALIAS,
        base_url=LLAMA_SWAP_BASE_URL,
        api_key="sk-llama-swap-local",
        use_responses_api=True,
        max_tokens=16384,
        temperature=0.1,
    )

    _record(
        {
            "phase": "A",
            "step": "invoke",
            "system_chars": len(COACH_SYSTEM_PROMPT),
            "user_chars": len(COACH_USER_PROMPT),
        }
    )

    ai_message = chat.invoke(
        [
            SystemMessage(content=COACH_SYSTEM_PROMPT),
            HumanMessage(content=COACH_USER_PROMPT),
        ]
    )

    # Summarise the shape — every reasoning location we know about.
    content_blocks_attr: Any
    try:
        content_blocks_attr = ai_message.content_blocks
    except Exception as exc:  # noqa: BLE001
        content_blocks_attr = {"error": f"{type(exc).__name__}: {exc}"}

    capture = {
        "class": type(ai_message).__name__,
        "module": type(ai_message).__module__,
        "id": getattr(ai_message, "id", None),
        "response_metadata_keys": sorted(getattr(ai_message, "response_metadata", {}).keys()),
        "usage_metadata": getattr(ai_message, "usage_metadata", None),
        "content": _summarize_content(ai_message.content),
        "additional_kwargs": _summarize_additional_kwargs(
            getattr(ai_message, "additional_kwargs", None)
        ),
        "content_blocks": (
            _summarize_content(content_blocks_attr)
            if not isinstance(content_blocks_attr, dict) or "error" not in content_blocks_attr
            else content_blocks_attr
        ),
    }
    return ai_message, capture


def phase_b_extractor(ai_message: Any) -> dict[str, Any]:
    """AC-2: drive the captured shape through ``extract_last_ai_reasoning``."""
    from guardkitfactory.harness.extractors import (
        extract_last_ai_message,
        extract_last_ai_reasoning,
    )

    result = {"messages": [ai_message]}
    canonical_text = extract_last_ai_message(result) or ""
    reasoning_text = extract_last_ai_reasoning(result)
    return {
        "canonical_text_len": len(canonical_text),
        "canonical_text_head": canonical_text[:400],
        "reasoning_text_len": len(reasoning_text),
        "reasoning_text_head": reasoning_text[:400],
        "ac2_pass": len(reasoning_text) > 0,
    }


def phase_c_parser(ai_message: Any, extractor: dict[str, Any]) -> dict[str, Any]:
    """AC-3: replay through ``coach_output_parser.extract_and_write``."""
    from guardkit.orchestrator.coach_output_parser import (
        CoachDecisionInvalidError,
        CoachDecisionNotFoundError,
        extract_and_write,
    )
    from guardkit.orchestrator.harness import AssistantMessageEvent, ResultMessageEvent

    from guardkitfactory.harness.extractors import (
        extract_last_ai_message,
        extract_last_ai_reasoning,
    )

    text = extract_last_ai_message({"messages": [ai_message]}) or ""
    reasoning_text = extract_last_ai_reasoning({"messages": [ai_message]})

    events = [
        AssistantMessageEvent(text=text, raw={}, reasoning_text=reasoning_text),
        ResultMessageEvent(session_id=None, stop_reason="end_turn", usage=None),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "coach_turn_1.json"
        out: dict[str, Any] = {
            "ac3_no_coachsf01": False,
            "coach_decision": None,
            "exception_class": None,
            "exception_message": None,
        }
        try:
            decision = extract_and_write(
                harness_events=events,
                task_id="TASK-FIX-IA03",
                turn=1,
                output_path=out_path,
            )
            out["ac3_no_coachsf01"] = True
            out["coach_decision"] = {
                "task_id": decision.get("task_id"),
                "turn": decision.get("turn"),
                "decision": decision.get("decision"),
                "feedback_len": (
                    len(decision.get("feedback", ""))
                    if isinstance(decision.get("feedback"), str)
                    else None
                ),
            }
        except CoachDecisionNotFoundError as exc:
            out["exception_class"] = "CoachDecisionNotFoundError"
            out["exception_message"] = str(exc)
        except CoachDecisionInvalidError as exc:
            out["exception_class"] = "CoachDecisionInvalidError"
            out["exception_message"] = str(exc)
        out["wrote_path_exists"] = out_path.exists()
    return out


def main() -> int:
    report: dict[str, Any] = {
        "task_id": "TASK-FIX-AC006SMOKE-LG",
        "model": COACH_MODEL_ALIAS,
        "base_url": LLAMA_SWAP_BASE_URL,
    }

    try:
        ai_message, capture = phase_a_capture()
    except Exception as exc:  # noqa: BLE001
        report["phase_a_error"] = {
            "class": type(exc).__name__,
            "message": str(exc),
            "trace": traceback.format_exc(),
        }
        (STATE_DIR / "probe_report.json").write_text(json.dumps(report, indent=2, default=str))
        _record({"verdict": "FAIL", "where": "phase_a"})
        return 2

    report["phase_a_capture"] = capture
    (STATE_DIR / "captured_aimessage.json").write_text(json.dumps(capture, indent=2, default=str))
    _record({"phase": "A", "result": "captured", "content_shape": capture["content"]["shape"]})

    try:
        extractor = phase_b_extractor(ai_message)
        report["phase_b_extractor"] = extractor
        _record(
            {
                "phase": "B",
                "ac2_pass": extractor["ac2_pass"],
                "reasoning_text_len": extractor["reasoning_text_len"],
            }
        )
    except Exception as exc:  # noqa: BLE001
        report["phase_b_error"] = {
            "class": type(exc).__name__,
            "message": str(exc),
            "trace": traceback.format_exc(),
        }
        (STATE_DIR / "probe_report.json").write_text(json.dumps(report, indent=2, default=str))
        _record({"verdict": "FAIL", "where": "phase_b"})
        return 3

    try:
        parser = phase_c_parser(ai_message, extractor)
        report["phase_c_parser"] = parser
        _record(
            {
                "phase": "C",
                "ac3_pass": parser["ac3_no_coachsf01"],
                "decision": parser["coach_decision"],
            }
        )
    except Exception as exc:  # noqa: BLE001
        report["phase_c_error"] = {
            "class": type(exc).__name__,
            "message": str(exc),
            "trace": traceback.format_exc(),
        }
        (STATE_DIR / "probe_report.json").write_text(json.dumps(report, indent=2, default=str))
        _record({"verdict": "FAIL", "where": "phase_c"})
        return 4

    ac2 = report["phase_b_extractor"]["ac2_pass"]
    ac3 = report["phase_c_parser"]["ac3_no_coachsf01"]
    overall = ac2 and ac3
    report["verdict"] = "PASS" if overall else "FAIL"
    report["ac_results"] = {
        "AC-1_capture": True,
        "AC-2_reasoning_text_positive": ac2,
        "AC-3_parser_recovers_verdict_no_COACHSF01": ac3,
    }

    (STATE_DIR / "probe_report.json").write_text(json.dumps(report, indent=2, default=str))
    _record({"verdict": report["verdict"], "ac2": ac2, "ac3": ac3})
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
