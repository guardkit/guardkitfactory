"""Third probe — fully serialise the reasoning block to see if plaintext lives
on a key the first two probes did not inspect (notably ``content``, which
shows up in probe B's ``keys`` list).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / "docs" / "state" / "TASK-FIX-AC006SMOKE-LG"

SYS_PROMPT = (
    "You are Coach. You evaluate Player turns adversarially. Think carefully before deciding."
)

USER_PROMPT = (
    "The Player just finished turn 1 of TASK-FIX-IA03. They report: 1 new file, "
    "2 modified, all tests passed, lint clean. The independent Coach test re-run "
    "also passed. Walk through whether you should approve or send feedback, and "
    "explain your reasoning step by step."
)


def _truncate(val, n=600):
    if isinstance(val, str):
        return val if len(val) <= n else val[:n] + f"…(+{len(val) - n} chars)"
    return val


def _dump_block(block):
    if not isinstance(block, dict):
        return {"raw": repr(block)[:200]}
    out = {}
    for k, v in block.items():
        if isinstance(v, str):
            out[k] = {"_str_len": len(v), "_str_head": _truncate(v)}
        elif isinstance(v, list):
            out[k] = {
                "_list_len": len(v),
                "_first_item": _truncate(repr(v[0])) if v else None,
                "_items": [
                    _dump_block(item) if isinstance(item, dict) else _truncate(repr(item))
                    for item in v
                ],
            }
        elif isinstance(v, dict):
            out[k] = _dump_block(v)
        else:
            out[k] = v
    return out


def main() -> int:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    chat = ChatOpenAI(
        model="gemma4-coach",
        base_url="http://localhost:9000/v1",
        api_key="sk-llama-swap-local",
        use_responses_api=True,
        max_tokens=16384,
        temperature=0.1,
    )

    print(json.dumps({"phase": "C", "step": "invoke"}))
    sys.stdout.flush()

    msg = chat.invoke([SystemMessage(content=SYS_PROMPT), HumanMessage(content=USER_PROMPT)])

    addl = getattr(msg, "additional_kwargs", {}) or {}
    content = msg.content

    dump = {
        "additional_kwargs": _dump_block(addl) if isinstance(addl, dict) else repr(addl)[:200],
        "content_type": ("str" if isinstance(content, str) else type(content).__name__),
    }

    if isinstance(content, list):
        dump["content_blocks"] = [_dump_block(b) for b in content]
    elif isinstance(content, str):
        dump["content"] = {"_str_len": len(content), "_str_head": _truncate(content)}

    # Also dump content_blocks property (langchain-core 1.4 normalised view)
    try:
        cb = msg.content_blocks
        if isinstance(cb, list):
            dump["content_blocks_property"] = [_dump_block(b) for b in cb]
        else:
            dump["content_blocks_property"] = repr(cb)[:200]
    except Exception as exc:  # noqa: BLE001
        dump["content_blocks_property_error"] = f"{type(exc).__name__}: {exc}"

    out_path = STATE_DIR / "captured_aimessage_probe_c.json"
    out_path.write_text(json.dumps(dump, indent=2, default=str))
    print(json.dumps({"phase": "C", "step": "dump_written", "path": str(out_path)}))

    # Now drive through the extractor + report
    from guardkitfactory.harness.extractors import (
        extract_last_ai_message,
        extract_last_ai_reasoning,
    )

    text = extract_last_ai_message({"messages": [msg]}) or ""
    reasoning = extract_last_ai_reasoning({"messages": [msg]})
    print(
        json.dumps(
            {
                "phase": "C",
                "extracted_text_len": len(text),
                "extracted_reasoning_len": len(reasoning),
                "reasoning_head": reasoning[:400],
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
