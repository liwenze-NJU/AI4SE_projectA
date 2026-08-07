"""Demo Scenario C — first test fails, feedback classified, repair, pass.

Runnable script (offline, mock only — no real LLM / network / API key).
Shows the full feedback loop: FAILED -> classified -> repaired -> PASSED.

Run:
    python demo/demo_scenario_c.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codeguard.demo.scenario_c import run_scenario_c
from codeguard.state import AgentState


def main() -> int:
    print("=" * 62)
    print("Demo Scenario C: fail -> classify -> repair -> COMPLETED")
    print("=" * 62)

    result = run_scenario_c()

    print("\nState machine transitions (trace):")
    for entry in result.trace:
        print(f"  {entry['from']}  ->  {entry['to']}")

    print("\nFeedback results:")
    for f in result.feedback_results:
        status = getattr(f, "status", "?")
        summary = str(getattr(f, "summary", ""))[:80]
        print(f"  [{status}] {summary}")

    print(f"\nFinal state: {result.terminal_state.value}")
    print(f"Steps: {result.steps_total} | LLM calls: {result.llm_calls_total} | "
          f"Tokens: {result.token_total}")
    return 0 if result.terminal_state == AgentState.COMPLETED else 1


if __name__ == "__main__":
    sys.exit(main())
