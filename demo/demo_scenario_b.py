"""Demo Scenario B — REQUEST_APPROVAL -> approve / reject / timeout.

Runnable script (offline, mock only — no real LLM / network / API key).
Shows the approval flow: approve -> COMPLETED, reject/timeout -> CANCELLED.

Run:
    python demo/demo_scenario_b.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codeguard.demo.scenario_b import (
    run_scenario_b_approve,
    run_scenario_b_reject,
    run_scenario_b_timeout,
)
from codeguard.state import AgentState


def _run(label: str, runner) -> int:
    print("=" * 62)
    print(f"Demo Scenario B: {label}")
    print("=" * 62)

    result = runner()

    print("\nState machine transitions (trace):")
    for entry in result.trace:
        print(f"  {entry['from']}  ->  {entry['to']}")

    print("\nGuardrail decisions:")
    for d in result.guardrail_decisions:
        action = d.normalized_action
        tool = f"{action.tool_name}({action.normalized_parameters})" if action else "-"
        print(f"  [{d.decision.value}] {tool}")
        print(f"        {d.human_readable_message}")

    print(f"\nFinal state: {result.terminal_state.value}")
    print(f"Steps: {result.steps_total} | LLM calls: {result.llm_calls_total}")
    return 0 if result.terminal_state == AgentState.COMPLETED else 1


def main() -> int:
    rc = _run("approve -> COMPLETED", run_scenario_b_approve)
    rc += _run("reject -> CANCELLED (zero executions)", run_scenario_b_reject)
    rc += _run("timeout -> CANCELLED (FakeClock, no real wait)", run_scenario_b_timeout)
    return rc


if __name__ == "__main__":
    sys.exit(main())
