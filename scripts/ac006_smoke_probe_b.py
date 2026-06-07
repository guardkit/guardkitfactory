"""Second probe — sanity-check whether ANY Coach-style prompt elicits non-empty
reasoning plaintext via /v1/responses on gemma4-coach.

The first probe (scripts/ac006_smoke_probe.py) used an explicit "end with a
fenced ```json block" instruction. This second probe drops that structural
instruction to see whether a more open-ended prompt yields a non-empty
reasoning block on the same transport.

Run from the factory repo root:

  PYTHONPATH=/home/richardwoollcott/Projects/appmilla_github/guardkit \\
  .venv/bin/python scripts/ac006_smoke_probe_b.py
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

    print(json.dumps({"phase": "B-2", "step": "invoke"}))
    sys.stdout.flush()

    msg = chat.invoke([SystemMessage(content=SYS_PROMPT), HumanMessage(content=USER_PROMPT)])

    # Summarise content + addl kwargs
    content = msg.content
    addl = getattr(msg, "additional_kwargs", {}) or {}

    summary = {
        "additional_kwargs_keys": sorted(addl.keys()),
        "content_shape": ("str" if isinstance(content, str) else type(content).__name__),
    }

    if isinstance(content, list):
        summary["block_types"] = [
            b.get("type") if isinstance(b, dict) else type(b).__name__ for b in content
        ]
        summary["blocks"] = []
        for b in content:
            if not isinstance(b, dict):
                summary["blocks"].append({"raw": repr(b)[:120]})
                continue
            block = {"type": b.get("type"), "keys": sorted(b.keys())}
            if "text" in b and isinstance(b["text"], str):
                block["text_len"] = len(b["text"])
                block["text_head"] = b["text"][:300]
            if "reasoning" in b and isinstance(b["reasoning"], str):
                block["reasoning_len"] = len(b["reasoning"])
                block["reasoning_head"] = b["reasoning"][:300]
            if "summary" in b:
                s = b["summary"]
                block["summary_len"] = len(s) if isinstance(s, list) else None
                if isinstance(s, list) and s:
                    block["summary_first"] = s[0]
            if "encrypted_content" in b and isinstance(b["encrypted_content"], str):
                block["encrypted_content_len"] = len(b["encrypted_content"])
            if "status" in b:
                block["status"] = b["status"]
            summary["blocks"].append(block)
    elif isinstance(content, str):
        summary["content_len"] = len(content)
        summary["content_head"] = content[:400]

    out_path = STATE_DIR / "captured_aimessage_probe_b.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2))

    # Quick verdict on whether reasoning plaintext appeared anywhere
    has_reasoning_plaintext = False
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "reasoning":
                if (
                    (isinstance(b.get("text"), str) and b["text"].strip())
                    or (isinstance(b.get("reasoning"), str) and b["reasoning"].strip())
                    or (isinstance(b.get("summary"), list) and b["summary"])
                ):
                    has_reasoning_plaintext = True
    if addl.get("reasoning_content") or addl.get("reasoning"):
        has_reasoning_plaintext = True

    print(json.dumps({"probe_b_has_reasoning_plaintext": has_reasoning_plaintext}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
