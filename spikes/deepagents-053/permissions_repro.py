"""ASSUM-008 verification: DeepAgents 0.5.3 permissions refuse writes at runtime.

Spike: TASK-SPIKE-C1E9 (parent review TASK-REV-A7D3 §5).

What this script does:
    1. Creates an isolated temp sandbox with `ok/` and `forbidden/` subdirs.
    2. Builds a `create_deep_agent` with `FilesystemBackend(root_dir=sandbox)`
       and `FilesystemPermission` rules that allow writes only under `ok/**`
       and deny everywhere else (including `forbidden/**`).
    3. Runs two separate agent invocations:
         (a) "write to forbidden path" — expected refusal.
         (b) "write to allowed path"   — expected success.
    4. Checks:
         - the forbidden file does NOT exist on disk.
         - the forbidden invocation's transcript contains a ToolMessage with
           a "permission denied" error.
         - (sanity) the allowed invocation created the allowed file on disk
           and did NOT produce a permission-denied ToolMessage.

Pass: forbidden write was refused at the tool layer AND the file is absent.
Fail: file was created, OR no permission-denied ToolMessage appeared.

Requires GOOGLE_API_KEY in the environment (Gemini via langchain-google-genai).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from deepagents import FilesystemPermission, create_deep_agent
from deepagents.backends import FilesystemBackend


def invoke_once(agent, user_msg: str) -> tuple[list, list]:
    """Invoke the agent and return (all_messages, tool_messages)."""
    result = agent.invoke({"messages": [{"role": "user", "content": user_msg}]})
    msgs = result["messages"]
    tool_msgs = [m for m in msgs if m.__class__.__name__ == "ToolMessage"]
    return msgs, tool_msgs


def describe(msgs) -> None:
    for m in msgs:
        kind = m.__class__.__name__
        content = str(getattr(m, "content", ""))[:180]
        tool_calls = getattr(m, "tool_calls", None) or []
        print(f"  [{kind}] content={content!r}")
        for tc in tool_calls:
            print(f"    -> tool_call name={tc.get('name')!r} args={tc.get('args')}")
        if kind == "ToolMessage":
            print(f"    status={getattr(m, 'status', None)!r}")


def main() -> int:
    sandbox = Path(tempfile.mkdtemp(prefix="spike_c1e9_perms_"))
    ok_dir = sandbox / "ok"
    forbidden_dir = sandbox / "forbidden"
    ok_dir.mkdir()
    forbidden_dir.mkdir()

    ok_target = ok_dir / "works.txt"
    forbidden_target = forbidden_dir / "out.txt"

    rules = [
        FilesystemPermission(
            operations=["write"],
            paths=[f"{ok_dir}/**"],
            mode="allow",
        ),
        FilesystemPermission(
            operations=["write"],
            paths=["/**"],
            mode="deny",
        ),
    ]

    backend = FilesystemBackend(root_dir=sandbox, virtual_mode=False)

    agent = create_deep_agent(
        model="google_genai:gemini-2.5-flash",
        permissions=rules,
        backend=backend,
        system_prompt=(
            "You are a test harness. When asked, call the write_file tool "
            "with the exact file_path and content given. If a tool returns "
            "an error, do not retry and do not paraphrase — just stop."
        ),
    )

    print(f"sandbox: {sandbox}")
    print(f"forbidden target: {forbidden_target}")
    print(f"allowed target:   {ok_target}")
    print()

    # -- Invocation A: forbidden write --------------------------------------
    print("=== Invocation A: forbidden write ===")
    msgs_a, tool_msgs_a = invoke_once(
        agent,
        f"Call write_file with file_path='{forbidden_target}' "
        f"and content='should_be_refused'.",
    )
    describe(msgs_a)

    denied_a = any(
        "permission denied" in str(getattr(m, "content", "")).lower()
        and str(forbidden_target) in str(getattr(m, "content", ""))
        for m in tool_msgs_a
    )
    forbidden_on_disk = forbidden_target.exists()

    # -- Invocation B: allowed write (sanity) --------------------------------
    print()
    print("=== Invocation B: allowed write (sanity) ===")
    msgs_b, tool_msgs_b = invoke_once(
        agent,
        f"Call write_file with file_path='{ok_target}' "
        f"and content='should_succeed'.",
    )
    describe(msgs_b)

    allowed_on_disk = ok_target.exists()
    denied_b = any(
        "permission denied" in str(getattr(m, "content", "")).lower()
        for m in tool_msgs_b
    )

    # -- Verdict -------------------------------------------------------------
    print()
    print("=" * 60)
    print("ASSUM-008 verdict")
    print("=" * 60)
    print(f"  A) forbidden file on disk?              {forbidden_on_disk}")
    print(f"  A) permission-denied ToolMessage seen?  {denied_a}")
    print(f"  B) allowed file on disk (sanity)?       {allowed_on_disk}")
    print(f"  B) permission-denied on allowed (sanity)? {denied_b}")

    pass_ = (not forbidden_on_disk) and denied_a
    if pass_:
        print("RESULT: PASS — permissions refused the forbidden write at "
              "runtime via a ToolMessage error; the file was never created.")
        shutil.rmtree(sandbox, ignore_errors=True)
        return 0
    else:
        print("RESULT: FAIL — permissions did not refuse the forbidden "
              "write as claimed by ASSUM-008.")
        print(f"sandbox retained for inspection: {sandbox}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
