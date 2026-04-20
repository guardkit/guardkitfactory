"""ASSUM-009 part 2: resume a paused LangGraph run from a separate process.

Spike: TASK-SPIKE-C1E9 (parent review TASK-REV-A7D3 §5).

Run `interrupt_graph.py` first to persist a paused checkpoint, then run
this script. This script:
    1. Opens the same `SqliteSaver`-backed checkpoint file.
    2. Rebuilds the compiled graph (structure is source-of-truth; the
       checkpointer restores state).
    3. Calls `graph.invoke(Command(resume=ApprovalDecision(...)), config)`
       where `config.thread_id` matches the paused run.
    4. Reads the resulting state and prints verdicts on:
         - type name of the resumed value the graph observed
         - `isinstance(decision, ApprovalDecision)` inside the node
         - type of the nested `decided_by` (expected: `Requestor`)
         - type of `decided_at` (expected: `datetime`)
         - that the graph ran past the interrupt to the `finalise` node
           (`finalised=True` in the final state)

Pass: the graph saw a fully-hydrated `ApprovalDecision` with nested
    Pydantic/UUID/datetime fields intact, and finished cleanly.
Fail: resumed value was a dict, or nested fields were strings/dicts, or
    the resume raised an exception, or the graph did not reach `finalise`.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from interrupt_graph import (
    ApprovalDecision,
    DB_PATH,
    Requestor,
    THREAD_ID,
    compiled_with_checkpointer,
)


def main() -> int:
    if not DB_PATH.exists():
        print(f"ERROR: no checkpoint at {DB_PATH}. "
              "Run interrupt_graph.py first.")
        return 2

    decision = ApprovalDecision(
        approved=True,
        decided_at=datetime.now(timezone.utc),
        decided_by=Requestor(id=uuid.uuid4(), handle="rich"),
        notes="approved via spike resume",
    )

    with SqliteSaver.from_conn_string(str(DB_PATH)) as checkpointer:
        graph = compiled_with_checkpointer(checkpointer)
        config = {"configurable": {"thread_id": THREAD_ID}}

        # Sanity: confirm we're actually paused before resume.
        paused_state = graph.get_state(config)
        print(f"paused at nodes: {paused_state.next}")

        print(f"resuming with {type(decision).__name__} instance:")
        print(f"  decision.approved = {decision.approved}")
        print(f"  decision.decided_by = {decision.decided_by}")
        print(f"  decision.decided_at = {decision.decided_at}")

        final = graph.invoke(Command(resume=decision), config=config)

    # --- Verdicts ----------------------------------------------------------
    print()
    print("=" * 60)
    print("ASSUM-009 verdict")
    print("=" * 60)
    print(f"  resumed value type name (seen by graph):  {final.get('decision_type_name')!r}")
    print(f"  isinstance(decision, ApprovalDecision):   {final.get('decision_is_pydantic')}")
    print(f"  nested decided_by type:                   {final.get('decision_decided_by_type')!r}")
    print(f"  decided_at type:                          {final.get('decision_decided_at_type')!r}")
    print(f"  decision.approved survived:               {final.get('decision_approved')}")
    print(f"  graph reached finalise node:              {final.get('finalised')}")

    ok = (
        final.get("decision_type_name") == "ApprovalDecision"
        and final.get("decision_is_pydantic") is True
        and final.get("decision_decided_by_type") == "Requestor"
        and final.get("decision_decided_at_type") == "datetime"
        and final.get("decision_approved") is True
        and final.get("finalised") is True
    )
    if ok:
        print("RESULT: PASS — typed Pydantic payload round-tripped through "
              "interrupt() + Command(resume=...) across process boundary.")
        return 0
    else:
        print("RESULT: FAIL — typed round-trip degraded (see verdict rows).")
        return 1


if __name__ == "__main__":
    sys.exit(main())
