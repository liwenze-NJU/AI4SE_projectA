"""Demo Scenario A — dangerous action BLOCKed, then safe action completes.

Runnable script (offline, mock only — no real LLM / network / API key).
Prints the full state-machine transitions and guardrail decisions.

Run:
    python demo/demo_scenario_a.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codeguard.demo.scenario_a import run_scenario_a
from codeguard.state import AgentState


def main() -> None:
    print("=" * 62)
    print("Demo Scenario A: BLOCK -> feedback -> COMPLETED")
    print("=" * 62)

    result = run_scenario_a()

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
    print(f"Steps: {result.steps_total} | LLM calls: {result.llm_calls_total} | "
          f"Tokens: {result.token_total}")
    return 0 if result.terminal_state == AgentState.COMPLETED else 1


if __name__ == "__main__":
    sys.exit(main())
